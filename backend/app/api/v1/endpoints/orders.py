from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Order, Client, Consultant, Payment, User
from app.models._time import utcnow
from app.schemas.marketplace import DeliverIn
from app.services import audit, payouts
from app.services.access import order_party
from app.services.realtime import publish_all
from app.services.serializers import order_out, payment_out

router = APIRouter()


def _get(db: Session, oid: int, user: User) -> tuple[Order, str]:
    o = db.get(Order, oid)
    party = order_party(user, o) if o else None
    if not o or not party:
        raise HTTPException(status_code=404, detail="Order not found")
    return o, party


def _other_party_ids(o: Order, party: str) -> list:
    ids = []
    if party != "client" and o.client and o.client.owner_user_id:
        ids.append(o.client.owner_user_id)
    if party != "freelancer" and o.consultant and o.consultant.user_id:
        ids.append(o.consultant.user_id)
    return ids


@router.get("", summary="My orders (client: bought, freelancer: received, admin: all)")
def list_orders(status: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Order)
    if user.role == "client":
        c = db.query(Client).filter(Client.owner_user_id == user.id).first()
        q = q.filter(Order.client_id == (c.id if c else -1))
    elif user.role == "freelancer":
        c = db.query(Consultant).filter(Consultant.user_id == user.id).first()
        q = q.filter(Order.consultant_id == (c.id if c else -1))
    if status:
        q = q.filter(Order.status == status)
    return [order_out(o) for o in q.order_by(Order.id.desc()).all()]


@router.get("/{order_id}", summary="One order with its payments")
def get_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o, party = _get(db, order_id, user)
    out = order_out(o)
    out["viewer_role"] = party
    out["payments"] = [payment_out(p) for p in db.query(Payment).filter(Payment.order_id == o.id)
                       .order_by(Payment.id.desc()).all()] if party in ("client", "admin") else []
    return out


@router.post("/{order_id}/cancel", summary="Cancel an unpaid order (client)")
def cancel(order_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o, party = _get(db, order_id, user)
    if party not in ("client", "admin"):
        raise HTTPException(status_code=403, detail="Only the client can cancel")
    if o.status != "pending_payment":
        raise HTTPException(status_code=400, detail="Only unpaid orders can be cancelled. Contact support for refunds.")
    o.status = "cancelled"
    if o.proposal_id:  # the job proposal goes back to the shortlist
        from app.models import Proposal
        p = db.get(Proposal, o.proposal_id)
        if p and p.status == "accepted":
            p.status = "shortlisted"
    db.commit()
    audit.log(db, "order.cancel", user.id, "order", o.id, None, request)
    return order_out(o)


@router.post("/{order_id}/deliver", summary="Mark work delivered (freelancer)")
async def deliver(order_id: int, payload: DeliverIn, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    o, party = _get(db, order_id, user)
    if party not in ("freelancer", "admin"):
        raise HTTPException(status_code=403, detail="Only the freelancer can deliver")
    if o.status != "in_progress":
        raise HTTPException(status_code=400, detail=f"Can't deliver an order that is {o.status.replace('_', ' ')}")
    o.status, o.delivered_at, o.delivery_note = "delivered", utcnow(), payload.delivery_note
    db.commit()
    audit.log(db, "order.deliver", user.id, "order", o.id, None, request)
    from app.services.notify import notify
    await publish_all(notify(db, o.client.owner_user_id if o.client else None, "delivered",
                             f"Order #{o.id} delivered — please review", f"{o.consultant.name} delivered “{o.title}”. "
                             "Approve it to release payment, or request changes.", f"/orders/{o.id}"))
    return order_out(o)


@router.post("/{order_id}/request-changes", summary="Send delivered work back for changes (client)")
def request_changes(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o, party = _get(db, order_id, user)
    if party not in ("client", "admin"):
        raise HTTPException(status_code=403, detail="Only the client can request changes")
    if o.status != "delivered":
        raise HTTPException(status_code=400, detail="Only delivered orders can be sent back")
    o.status = "in_progress"
    db.commit()
    from app.services.notify import notify
    notify(db, o.consultant.user_id if o.consultant else None, "changes_requested",
           f"Changes requested on order #{o.id}", f"The client sent “{o.title}” back for changes.", f"/orders/{o.id}")
    return order_out(o)


@router.post("/{order_id}/complete", summary="Approve delivered work (client) — queues the freelancer payout")
async def complete(order_id: int, request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    o, party = _get(db, order_id, user)
    if party not in ("client", "admin"):
        raise HTTPException(status_code=403, detail="Only the client can approve")
    if o.status != "delivered":
        raise HTTPException(status_code=400, detail="Only delivered orders can be approved")
    o.status, o.completed_at, o.payout_status = "completed", utcnow(), "pending"
    db.commit()
    audit.log(db, "order.complete", user.id, "order", o.id, None, request)
    result = payouts.release(db, o)
    if result.get("ok"):
        audit.log(db, "payout.auto_release", user.id, "order", o.id,
                  {"transfer_id": o.transfer_id, "mode": o.payout_mode}, request)
    from app.services.notify import notify
    from app.services.serializers import rupees
    paid = o.payout_status == "released"
    msg = (f"The client approved “{o.title}”. {rupees(o.amount_paise - o.platform_fee_paise):,} {o.currency} "
           + ("has been released to your payout account." if paid else
              "will be paid out to you — check the Payouts page."))
    await publish_all(notify(db, o.consultant.user_id if o.consultant else None, "approved",
                             f"Order #{o.id} approved", msg, "/freelancer/payouts"))
    return order_out(o)
