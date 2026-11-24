from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.deps import get_current_user, current_freelancer
from app.models import Proposal, Consultant, Order, User
from app.services import audit
from app.services.access import owns_job
from app.services.realtime import publish_all
from app.services.serializers import proposal_out, order_out

router = APIRouter()


def _get(db: Session, pid: int) -> Proposal:
    p = db.get(Proposal, pid)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return p


@router.get("/mine", summary="My proposals (freelancer)")
def mine(me: Consultant = Depends(current_freelancer), db: Session = Depends(get_db)):
    rows = db.query(Proposal).filter(Proposal.consultant_id == me.id).order_by(Proposal.id.desc()).all()
    out = []
    for p in rows:
        d = proposal_out(p, with_job=True)
        o = db.query(Order).filter(Order.proposal_id == p.id).first()
        d["order_id"] = o.id if o else None
        out.append(d)
    return out


@router.post("/{proposal_id}/withdraw", summary="Withdraw my proposal")
def withdraw(proposal_id: int, me: Consultant = Depends(current_freelancer), db: Session = Depends(get_db)):
    p = _get(db, proposal_id)
    if p.consultant_id != me.id:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if p.status not in ("submitted", "shortlisted"):
        raise HTTPException(status_code=400, detail=f"A {p.status} proposal can't be withdrawn")
    p.status = "withdrawn"
    db.commit()
    return proposal_out(p, with_job=True)


def _owned_by_client(db: Session, p: Proposal, user: User):
    if not owns_job(db, user, p.job):
        raise HTTPException(status_code=404, detail="Proposal not found")


@router.post("/{proposal_id}/shortlist", summary="Shortlist a proposal (job owner)")
def shortlist(proposal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _get(db, proposal_id)
    _owned_by_client(db, p, user)
    if p.status != "submitted":
        raise HTTPException(status_code=400, detail=f"Can't shortlist a {p.status} proposal")
    p.status = "shortlisted"
    db.commit()
    return proposal_out(p, with_freelancer=True)


@router.post("/{proposal_id}/reject", summary="Decline a proposal (job owner)")
def reject(proposal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _get(db, proposal_id)
    _owned_by_client(db, p, user)
    if p.status not in ("submitted", "shortlisted"):
        raise HTTPException(status_code=400, detail=f"Can't decline a {p.status} proposal")
    p.status = "rejected"
    db.commit()
    from app.services.notify import notify
    notify(db, p.consultant.user_id if p.consultant else None, "proposal_declined",
           f"Proposal not selected: “{p.job.title}”", "The client chose another freelancer this time.",
           "/freelancer/proposals", send_email=False)
    return proposal_out(p, with_freelancer=True)


@router.post("/{proposal_id}/accept", summary="Hire: accept a proposal and create an order to pay for")
async def accept(proposal_id: int, request: Request, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    p = _get(db, proposal_id)
    _owned_by_client(db, p, user)
    if p.status not in ("submitted", "shortlisted"):
        raise HTTPException(status_code=400, detail=f"Can't accept a {p.status} proposal")
    amount = p.bid_amount * 100
    order = Order(client_id=p.job.client_id, consultant_id=p.consultant_id, job_id=p.job_id, proposal_id=p.id,
                  currency=p.job.currency or "INR",
                  title=p.job.title, amount_paise=amount,
                  platform_fee_paise=round(amount * config.PLATFORM_FEE_PERCENT / 100), status="pending_payment")
    p.status = "accepted"
    db.add(order)
    db.commit()
    db.refresh(order)
    audit.log(db, "proposal.accept", user.id, "proposal", p.id, {"order_id": order.id}, request)
    from app.services.notify import notify
    await publish_all(notify(db, p.consultant.user_id if p.consultant else None, "hired",
                             f"You're hired for “{p.job.title}”", "The client accepted your proposal. Work starts as "
                             "soon as they pay — you'll get another notification.", f"/orders/{order.id}"))
    return order_out(order)
