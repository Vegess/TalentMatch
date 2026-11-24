import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.deps import get_current_user, current_client
from app.core.plans import PLANS, normalize_plan, price
from app.core.ratelimit import limit
from app.models import Payment, Order, Client, User
from app.schemas.marketplace import CheckoutIn, VerifyIn, DemoCompleteIn
from app.services import payments as pay, audit
from app.services.realtime import publish_all
from app.services.serializers import payment_out

router = APIRouter()


@router.get("/config", summary="Which payment provider handles each currency (public key only)")
def payment_config():
    return {"provider": pay.provider(), "providers": pay.providers_summary(),
            "key_id": config.RAZORPAY_KEY_ID if pay.razorpay_on() else None,
            "currencies": list(config.CURRENCIES), "platform_fee_percent": config.PLATFORM_FEE_PERCENT,
            "demo": pay.demo_allowed()}


@router.post("/checkout", summary="Start a payment (plan upgrade or an order)",
             dependencies=[Depends(limit("checkout", 20, 60))])
def checkout(payload: CheckoutIn, request: Request, client: Client = Depends(current_client),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.purpose == "subscription":
        try:
            plan = normalize_plan(payload.plan_type or "")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        currency = client.currency or "INR"
        unit = price(plan, currency)
        if unit <= 0:
            raise HTTPException(status_code=400, detail="The FREE plan doesn't need a payment")
        amount = unit * payload.months * 100
        description = f"{PLANS[plan]['name']} plan · {payload.months} month(s)"
        p = Payment(user_id=user.id, client_id=client.id, purpose="subscription", plan_type=plan,
                    months=payload.months, amount_paise=amount, currency=currency, provider="pending",
                    provider_order_id="pending")
    else:
        o = db.get(Order, payload.order_id or 0)
        if not o or o.client_id != client.id:
            raise HTTPException(status_code=404, detail="Order not found")
        if o.status != "pending_payment":
            raise HTTPException(status_code=400, detail="This order is already paid or cancelled")
        currency, amount = o.currency, o.amount_paise
        description = f"Order #{o.id} · {o.title}"
        p = Payment(user_id=user.id, client_id=client.id, purpose="order", order_id=o.id, amount_paise=amount,
                    currency=currency, provider="pending", provider_order_id="pending")
    p.provider = pay.provider_for(currency)
    db.add(p)
    db.flush()
    p.provider_order_id = f"pending_{p.id}"
    checkout_url = None
    try:
        if p.provider == "stripe":
            s = pay.create_stripe_session(p, description, user.email)
            p.provider_order_id, checkout_url = s["id"], s["url"]
        else:
            p.provider_order_id = pay.create_provider_order(amount, f"tm_{p.id}", {"payment_id": str(p.id),
                                                                                  "purpose": p.purpose})
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    db.refresh(p)
    audit.log(db, "payment.checkout", user.id, "payment", p.id,
              {"amount_minor": amount, "currency": currency, "purpose": p.purpose, "provider": p.provider}, request)
    return {"payment_id": p.id, "provider": p.provider, "key_id": config.RAZORPAY_KEY_ID or None,
            "provider_order_id": p.provider_order_id, "checkout_url": checkout_url, "amount_paise": amount,
            "amount_minor": amount, "currency": p.currency, "description": description,
            "prefill": {"name": user.name, "email": user.email}}


def _own_payment(db: Session, payment_id: int, user: User) -> Payment:
    p = db.get(Payment, payment_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    return p


@router.post("/verify", summary="Confirm a Razorpay checkout (signature check)")
async def verify(payload: VerifyIn, request: Request, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    p = _own_payment(db, payload.payment_id, user)
    if p.provider != "razorpay" or p.provider_order_id != payload.razorpay_order_id:
        raise HTTPException(status_code=400, detail="Payment details don't match")
    if not pay.checkout_signature_ok(payload.razorpay_order_id, payload.razorpay_payment_id,
                                     payload.razorpay_signature):
        audit.log(db, "payment.bad_signature", user.id, "payment", p.id, None, request)
        raise HTTPException(status_code=400, detail="Payment signature is invalid")
    events = pay.fulfil(db, p, payload.razorpay_payment_id)
    audit.log(db, "payment.paid", user.id, "payment", p.id, {"provider": "razorpay"}, request)
    await publish_all(events)
    return payment_out(p)


class StripeConfirmIn(BaseModel):
    payment_id: int
    session_id: str = Field(..., max_length=255)


@router.post("/stripe/confirm", summary="Confirm a Stripe Checkout after the redirect back")
async def stripe_confirm(payload: StripeConfirmIn, request: Request, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    p = _own_payment(db, payload.payment_id, user)
    if p.provider != "stripe" or p.provider_order_id != payload.session_id:
        raise HTTPException(status_code=400, detail="Payment details don't match")
    if p.status == "paid":
        return payment_out(p)
    session = pay._stripe("GET", f"/checkout/sessions/{payload.session_id}")
    if not pay.stripe_session_paid(p, session):
        return payment_out(p)  # still processing (e.g. bank debit) — the webhook will finish it
    events = pay.fulfil(db, p, session.get("payment_intent"))
    audit.log(db, "payment.paid", user.id, "payment", p.id, {"provider": "stripe"}, request)
    await publish_all(events)
    return payment_out(p)


@router.post("/{payment_id}/demo-complete", summary="Finish a simulated payment (demo mode only)")
async def demo_complete(payment_id: int, payload: DemoCompleteIn, request: Request,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _own_payment(db, payment_id, user)
    if p.provider != "demo" or not pay.demo_allowed():
        raise HTTPException(status_code=400, detail="Demo payments are disabled")
    if payload.outcome == "failure":
        pay.mark_failed(db, p, "Payment declined (demo)")
        return payment_out(p)
    events = pay.fulfil(db, p, "demo_pay_" + p.provider_order_id[-8:])
    audit.log(db, "payment.paid", user.id, "payment", p.id, {"provider": "demo"}, request)
    await publish_all(events)
    return payment_out(p)


@router.post("/{payment_id}/failed", summary="Record a failed / dismissed checkout")
def failed(payment_id: int, reason: str = "Checkout closed", user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    p = _own_payment(db, payment_id, user)
    pay.mark_failed(db, p, reason)
    return payment_out(p)


@router.post("/webhook", summary="Razorpay webhook (payments + Route events)")
async def webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    if not pay.webhook_signature_ok(body, request.headers.get("x-razorpay-signature", "")):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    try:
        event = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad JSON")
    kind = event.get("event", "")
    from app.services import payouts
    route_result = payouts.handle_webhook(db, event)
    if route_result is not None:
        if route_result == "ok":
            audit.log(db, f"webhook.{kind}", None, None, None, None)
        return {"status": route_result}
    entity = (event.get("payload", {}).get("payment") or {}).get("entity") or {}
    order_id = entity.get("order_id") or ((event.get("payload", {}).get("order") or {}).get("entity") or {}).get("id")
    p = db.query(Payment).filter(Payment.provider_order_id == order_id).first() if order_id else None
    if not p:
        return {"status": "ignored"}
    if kind in ("payment.captured", "order.paid"):
        if entity.get("amount") is not None and int(entity["amount"]) != p.amount_paise:
            audit.log(db, "payment.amount_mismatch", None, "payment", p.id, {"paid": entity.get("amount")})
            return {"status": "amount_mismatch"}
        events = pay.fulfil(db, p, entity.get("id"))
        audit.log(db, "payment.paid", None, "payment", p.id, {"via": "webhook"})
        await publish_all(events)
    elif kind == "payment.failed":
        pay.mark_failed(db, p, entity.get("error_description") or "Payment failed")
    return {"status": "ok"}


@router.post("/stripe/webhook", summary="Stripe webhook (checkout.session.*)")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    if not pay.stripe_signature_ok(body, request.headers.get("stripe-signature", "")):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    try:
        event = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad JSON")
    kind = event.get("type", "")
    session = (event.get("data") or {}).get("object") or {}
    p = db.query(Payment).filter(Payment.provider_order_id == session.get("id"), Payment.provider == "stripe").first() \
        if session.get("id") else None
    if not p:
        return {"status": "ignored"}
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if not pay.stripe_session_paid(p, session):
            if session.get("payment_status") == "paid":  # paid, but not the amount we asked for
                audit.log(db, "payment.amount_mismatch", None, "payment", p.id,
                          {"paid": session.get("amount_total"), "currency": session.get("currency")})
                return {"status": "amount_mismatch"}
            return {"status": "pending"}
        events = pay.fulfil(db, p, session.get("payment_intent"))
        audit.log(db, "payment.paid", None, "payment", p.id, {"via": "stripe_webhook"})
        await publish_all(events)
    elif kind in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        pay.mark_failed(db, p, "Payment failed" if "failed" in kind else "Checkout expired")
    return {"status": "ok"}


@router.get("/mine", summary="My payment history")
def mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [payment_out(p) for p in db.query(Payment).filter(Payment.user_id == user.id)
            .order_by(Payment.id.desc()).all()]


@router.get("/{payment_id}", summary="One of my payments")
def get_payment(payment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return payment_out(_own_payment(db, payment_id, user))
