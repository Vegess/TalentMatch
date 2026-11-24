from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_client, require_admin
from app.core.plans import PLANS
from app.models import Subscription, Client, User
from app.services import subscriptions as subs, audit

router = APIRouter()


@router.get("/plans", summary="Plans and limits (public)")
def plans():
    return [{"plan_type": k, **v} for k, v in PLANS.items()]


@router.get("/me", summary="My active plan, usage and history")
def my_subscription(client: Client = Depends(current_client), db: Session = Depends(get_db)):
    active = subs.get_active(db, client.id)
    history = db.query(Subscription).filter(Subscription.client_id == client.id).order_by(Subscription.id.desc()).all()
    return {"active": subs.subscription_out(active) if active else None,
            "limits": PLANS.get(active.plan_type) if active else None,
            "open_jobs": subs.open_job_count(db, client.id),
            "history": [subs.subscription_out(s) for s in history]}


@router.post("/downgrade", summary="Switch to the FREE plan (cancels the paid plan now)")
def downgrade(request: Request, client: Client = Depends(current_client), db: Session = Depends(get_db)):
    active = subs.get_active(db, client.id)
    if active and active.plan_type == "FREE":
        raise HTTPException(status_code=400, detail="You're already on the FREE plan")
    s = subs.start_subscription(db, client.id, "FREE")
    audit.log(db, "subscription.downgrade", client.owner_user_id, "client", client.id, None, request)
    return subs.subscription_out(s)


class GrantIn(BaseModel):
    client_id: int
    plan_type: str
    months: int | None = Field(None, ge=1, le=36)


@router.post("/grant", summary="Admin: give a client a plan without payment")
def grant(payload: GrantIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    s = subs.start_subscription(db, payload.client_id, payload.plan_type, months=payload.months)
    audit.log(db, "subscription.grant", admin.id, "client", payload.client_id,
              {"plan": s.plan_type, "months": payload.months}, request)
    return subs.subscription_out(s)
