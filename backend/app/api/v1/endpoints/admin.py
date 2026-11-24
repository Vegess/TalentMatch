"""Control room: platform-wide numbers, users, money, moderation and audit trail. Admins only."""
import datetime as dt
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.deps import require_admin
from app.core.plans import PLANS
from app.models import (User, Client, Consultant, Job, Match, Subscription, Service, Proposal, Order, Payment,
                        AuditLog, AuthSession, Document)
from app.models._time import utcnow
from app.services import audit, matching, subscriptions as subs
from app.services.serializers import (user_admin_out, order_out, payment_out, job_out, service_out, rupees)

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/overview", summary="KPIs, revenue and activity (money split by currency)")
def overview(days: int = Query(30, ge=7, le=365), db: Session = Depends(get_db)):
    from app.services import payouts as _p, payments as _pay
    from app.core.plans import price
    subs.expire_old(db)
    now = utcnow()
    since = now - dt.timedelta(days=days)
    currencies = list(config.CURRENCIES)
    paid = db.query(Payment).filter(Payment.status == "paid").all()
    orders = db.query(Order).all()

    def money_for(cur: str) -> dict:
        ps = [p for p in paid if p.currency == cur]
        os_ = [o for o in orders if o.currency == cur]
        earn = lambda o: o.amount_paise - o.platform_fee_paise  # noqa: E731
        return {
            "total_collected": rupees(sum(p.amount_paise for p in ps)),
            "subscription_revenue": rupees(sum(p.amount_paise for p in ps if p.purpose == "subscription")),
            "order_gmv": rupees(sum(o.amount_paise for o in os_ if o.paid_at)),
            "platform_fees": rupees(sum(o.platform_fee_paise for o in os_ if o.paid_at)),
            "payouts_pending": rupees(sum(earn(o) for o in os_ if o.payout_status in ("pending", "failed"))),
            "payouts_held": rupees(sum(earn(o) for o in os_ if o.payout_status == "held")),
            "payouts_released": rupees(sum(earn(o) for o in os_ if o.payout_status == "released")),
        }

    by_currency = {c: money_for(c) for c in currencies}
    used = [c for c in currencies if c == "INR" or any(v for v in by_currency[c].values())]

    day_rev = {c: defaultdict(int) for c in currencies}
    for p in paid:
        if p.paid_at and p.paid_at >= since and p.currency in day_rev:
            day_rev[p.currency][p.paid_at.date().isoformat()] += p.amount_paise
    signups_by_day = defaultdict(int)
    for (created,) in db.query(User.created_at).filter(User.created_at >= since).all():
        signups_by_day[created.date().isoformat()] += 1
    series = []
    for i in range(days - 1, -1, -1):
        d = (now - dt.timedelta(days=i)).date().isoformat()
        row = {"date": d, "signups": signups_by_day.get(d, 0), "revenue": rupees(day_rev["INR"].get(d, 0))}
        for c in currencies:
            row[f"revenue_{c}"] = rupees(day_rev[c].get(d, 0))
        series.append(row)

    plan_split = {k: 0 for k in PLANS}
    mrr = {c: 0 for c in currencies}
    for s in db.query(Subscription).filter(Subscription.status == "active").all():
        plan_split[s.plan_type] = plan_split.get(s.plan_type, 0) + 1
        cur = s.client.currency if s.client else "INR"
        mrr[cur] = mrr.get(cur, 0) + price(s.plan_type, cur)
    order_status = defaultdict(int)
    for o in orders:
        order_status[o.status] += 1
    countries = defaultdict(int)
    for (cc,) in db.query(Consultant.country).all():
        countries[cc or "—"] += 1
    for (cc,) in db.query(Client.country).all():
        countries[cc or "—"] += 1
    money = {**by_currency["INR"], "mrr": mrr["INR"],
             "failed_payments": db.query(Payment).filter(Payment.status == "failed").count(),
             "payouts_failed": sum(1 for o in orders if o.payout_status == "failed")}
    return {
        "users": {"total": db.query(User).count(),
                  "clients": db.query(User).filter(User.role == "client").count(),
                  "freelancers": db.query(User).filter(User.role == "freelancer").count(),
                  "disabled": db.query(User).filter(User.is_active.is_(False)).count()},
        "marketplace": {"freelancer_profiles": db.query(Consultant).count(),
                        "open_jobs": db.query(Job).filter(Job.status == "open").count(),
                        "jobs": db.query(Job).count(),
                        "active_services": db.query(Service).filter(Service.status == "active").count(),
                        "proposals": db.query(Proposal).count(), "matches": db.query(Match).count(),
                        "documents": db.query(Document).count()},
        "money": money, "money_by_currency": {c: {**by_currency[c], "mrr": mrr[c]} for c in used},
        "currencies_in_use": used,
        "plans": plan_split, "orders_by_status": dict(order_status), "series": series,
        "countries": dict(sorted(countries.items(), key=lambda kv: -kv[1])[:12]),
        "payment_provider": config.PAYMENT_PROVIDER, "payment_providers": _pay.providers_summary(),
        "payout_mode": _p.mode(),
        "freelancers_with_payouts": db.query(Consultant).filter(Consultant.payout_account_id.isnot(None)).count(),
        "match_threshold": config.MATCH_THRESHOLD, "signup_mode": config.SIGNUP_MODE,
        "email": "smtp" if config.SMTP_HOST else "log",
    }


@router.get("/users", summary="Users (search by name/email, filter by role)")
def users(q: Optional[str] = None, role: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(User)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    if role:
        query = query.filter(User.role == role)
    return [user_admin_out(u) for u in query.order_by(User.id.desc()).limit(500).all()]


class UserPatch(BaseModel):
    is_active: Optional[bool] = None
    verified: Optional[bool] = None  # identity checked by the team → "Verified" badge


@router.patch("/users/{user_id}", summary="Disable / re-enable an account")
def patch_user(user_id: int, payload: UserPatch, request: Request, admin: User = Depends(require_admin),
               db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="You can't disable your own account")
    if payload.is_active is not None:
        u.is_active = payload.is_active
        if not payload.is_active:  # end their sessions right away
            db.query(AuthSession).filter(AuthSession.user_id == u.id, AuthSession.revoked_at.is_(None)) \
                .update({AuthSession.revoked_at: utcnow()})
    if payload.verified is not None:
        target = u.client if u.role == "client" else u.consultant if u.role == "freelancer" else None
        if not target:
            raise HTTPException(status_code=400, detail="Only clients and freelancers can be verified")
        target.verified_at = utcnow() if payload.verified else None
    db.commit()
    if payload.is_active is not None:
        audit.log(db, "user.enable" if u.is_active else "user.disable", admin.id, "user", u.id, None, request)
    if payload.verified is not None:
        audit.log(db, "user.verify" if payload.verified else "user.unverify", admin.id, "user", u.id, None, request)
        if payload.verified:
            from app.services.notify import notify
            notify(db, u.id, "verified", "Your account is verified", "You now show a Verified badge on TalentMatch.",
                   "/settings", send_email=True)
    return user_admin_out(u)


@router.get("/payments", summary="Payment ledger")
def payments(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Payment)
    if status:
        q = q.filter(Payment.status == status)
    return [payment_out(p) for p in q.order_by(Payment.id.desc()).limit(500).all()]


@router.get("/orders", summary="All orders")
def orders(status: Optional[str] = None, payout_status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Order)
    if status:
        q = q.filter(Order.status == status)
    if payout_status:
        q = q.filter(Order.payout_status == payout_status)
    return [order_out(o) for o in q.order_by(Order.id.desc()).limit(500).all()]


@router.post("/orders/{order_id}/release-payout", summary="Record that the freelancer has been paid out")
def release_payout(order_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.status != "completed" or o.payout_status not in ("pending", "failed"):
        raise HTTPException(status_code=400, detail="This order has no payout waiting for manual release")
    o.payout_status, o.payout_mode, o.payout_error, o.payout_released_at = "released", "manual", None, utcnow()
    db.commit()
    audit.log(db, "payout.release", admin.id, "order", o.id,
              {"amount": rupees(o.amount_paise - o.platform_fee_paise)}, request)
    return order_out(o)


@router.post("/orders/{order_id}/retry-payout", summary="Retry the automatic (Route) payout")
def retry_payout(order_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from app.services import payouts
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.status != "completed" or o.payout_status not in ("pending", "failed"):
        raise HTTPException(status_code=400, detail="Only approved orders with a pending or failed payout can be retried")
    result = payouts.release(db, o)
    audit.log(db, "payout.retry", admin.id, "order", o.id, {"result": o.payout_status, "error": o.payout_error}, request)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=o.payout_error or "Payout still not possible")
    return order_out(o)


@router.get("/jobs", summary="All jobs (any status)")
def jobs(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    return [job_out(db, j, owner_view=True) for j in q.order_by(Job.id.desc()).limit(500).all()]


@router.get("/services", summary="All services (any status)")
def services(db: Session = Depends(get_db)):
    return [service_out(s) for s in db.query(Service).order_by(Service.id.desc()).limit(500).all()]


@router.get("/audit", summary="Audit trail (newest first)")
def audit_log(action: Optional[str] = None, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action.ilike(f"{action}%"))
    rows = q.order_by(AuditLog.id.desc()).limit(limit).all()
    names = {u.id: u.email for u in db.query(User).filter(User.id.in_({r.actor_user_id for r in rows if r.actor_user_id})).all()}
    return [{"id": r.id, "action": r.action, "actor_user_id": r.actor_user_id, "actor": names.get(r.actor_user_id),
             "target_type": r.target_type, "target_id": r.target_id, "details": r.details, "ip": r.ip,
             "created_at": r.created_at} for r in rows]


@router.post("/rematch-all", summary="Recompute every match (after changing weights or threshold)")
def rematch_all(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    n = matching.rematch_all(db)
    audit.log(db, "matching.rematch_all", admin.id, None, None, {"jobs": n}, request)
    return {"status": "ok", "jobs_rematched": n}
