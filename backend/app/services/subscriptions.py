import datetime
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.plans import normalize_plan, plan_limits, DEFAULT_PLAN
from app.models import Subscription, Job, Client
from app.models._time import utcnow


def expire_old(db: Session, client_id: Optional[int] = None):
    q = db.query(Subscription).filter(Subscription.status == "active", Subscription.end_date.isnot(None),
                                      Subscription.end_date <= utcnow())
    if client_id is not None:
        q = q.filter(Subscription.client_id == client_id)
    rows = q.all()
    for s in rows:
        s.status = "expired"
    if rows:
        db.commit()


def get_active(db: Session, client_id: int) -> Optional[Subscription]:
    expire_old(db, client_id)
    return (db.query(Subscription).filter(Subscription.client_id == client_id, Subscription.status == "active")
            .order_by(Subscription.id.desc()).first())


def start_subscription(db: Session, client_id: int, plan_type: str, months: Optional[int] = None,
                       start_date: Optional[datetime.datetime] = None,
                       end_date: Optional[datetime.datetime] = None,
                       payment_id: Optional[int] = None, commit: bool = True) -> Subscription:
    """Start a plan. Any active plan is cancelled (upgrade / downgrade)."""
    try:
        plan = normalize_plan(plan_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="Client not found")
    start = start_date or utcnow()
    if end_date is None and months:
        end_date = start + datetime.timedelta(days=30 * months)
    if end_date is not None and end_date <= start:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")
    for s in db.query(Subscription).filter(Subscription.client_id == client_id,
                                           Subscription.status == "active").all():
        s.status = "cancelled"
        if s.end_date is None or s.end_date > start:
            s.end_date = start
    sub = Subscription(client_id=client_id, plan_type=plan, status="active", start_date=start,
                       end_date=end_date, payment_id=payment_id)
    db.add(sub)
    if commit:
        db.commit()
        db.refresh(sub)
    else:
        db.flush()
    return sub


def current_plan(db: Session, client_id: int) -> Optional[str]:
    sub = get_active(db, client_id)
    return sub.plan_type if sub else None


def open_job_count(db: Session, client_id: int, exclude_job_id: Optional[int] = None) -> int:
    q = db.query(Job).filter(Job.client_id == client_id, Job.status == "open")
    if exclude_job_id:
        q = q.filter(Job.id != exclude_job_id)
    return q.count()


def ensure_can_open_job(db: Session, client_id: int, exclude_job_id: Optional[int] = None):
    sub = get_active(db, client_id)
    if not sub:
        raise HTTPException(status_code=403, detail="No active plan. Choose a plan before posting jobs.")
    limit = plan_limits(sub.plan_type)["max_open_jobs"]
    if limit is not None and open_job_count(db, client_id, exclude_job_id) >= limit:
        raise HTTPException(status_code=403, detail=f"Your {sub.plan_type} plan allows {limit} open job(s). "
                                                    f"Close a job or upgrade your plan.")


def subscription_out(s: Subscription) -> dict:
    return {"id": s.id, "client_id": s.client_id, "plan_type": s.plan_type, "status": s.status,
            "start_date": s.start_date, "end_date": s.end_date, "is_active": s.is_active(),
            "payment_id": s.payment_id}


DEFAULT = DEFAULT_PLAN
