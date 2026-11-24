"""Payments: Razorpay (INR), Stripe (USD / EUR / GBP) and the single place where a payment is fulfilled.

Razorpay: POST /payments/checkout creates a Payment row + a Razorpay order → Razorpay Checkout in the browser →
POST /payments/verify checks the signature (HMAC-SHA256 of "order_id|payment_id") → fulfil().
Stripe: checkout creates a Stripe Checkout Session → the browser is redirected to Stripe → back on
/payments/return the app calls /payments/stripe/confirm, which re-reads the session from Stripe → fulfil().
Both providers' webhooks call the same fulfil(), so a payment is credited even if the browser closes. fulfil() is
idempotent.

Demo mode: only when NO real provider is configured, a simulated checkout that moves no money.
"""
import hashlib
import hmac
import secrets
import time
from typing import List, Dict, Any, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core import config
from app.models import Payment, Order
from app.models._time import utcnow
from app.services import subscriptions as subs

RAZORPAY_API = "https://api.razorpay.com/v1"
STRIPE_API = "https://api.stripe.com/v1"


def razorpay_on() -> bool:
    return config.PAYMENT_PROVIDER == "razorpay"


def stripe_on() -> bool:
    return bool(config.STRIPE_SECRET_KEY)


def demo_allowed() -> bool:
    """Simulated payments are only possible while no real provider is configured."""
    return not razorpay_on() and not stripe_on()


def provider() -> str:  # kept for older callers: the INR provider
    return provider_for("INR", strict=False) or "demo"


def provider_for(currency: str, strict: bool = True) -> Optional[str]:
    currency = (currency or "INR").upper()
    if currency not in config.CURRENCIES:
        if strict:
            raise HTTPException(status_code=400, detail=f"Currency {currency} isn't supported")
        return None
    if currency == "INR" and razorpay_on():
        return "razorpay"
    if stripe_on():
        return "stripe"
    if demo_allowed():
        return "demo"
    if strict:
        raise HTTPException(status_code=400, detail=f"Payments in {currency} aren't available yet on this platform.")
    return None


def providers_summary() -> Dict[str, Optional[str]]:
    return {c: provider_for(c, strict=False) for c in config.CURRENCIES}


# ---- Razorpay ---------------------------------------------------------------------------------------
def create_provider_order(amount_paise: int, receipt: str, notes: Dict[str, str]) -> str:
    """Razorpay order (INR) — or a demo order id when no provider is configured."""
    if not razorpay_on():
        return "demo_order_" + secrets.token_hex(8)
    try:
        r = httpx.post(f"{RAZORPAY_API}/orders", auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET),
                       json={"amount": amount_paise, "currency": "INR", "receipt": receipt[:40],
                             "notes": notes}, timeout=15)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Payment provider unreachable: {e}")
    if r.status_code >= 300:
        detail = r.json().get("error", {}).get("description", r.text) if r.headers.get(
            "content-type", "").startswith("application/json") else r.text
        raise HTTPException(status_code=502, detail=f"Razorpay error: {detail}")
    return r.json()["id"]


def checkout_signature_ok(order_id: str, payment_id: str, signature: str) -> bool:
    if not config.RAZORPAY_KEY_SECRET:
        return False
    expected = hmac.new(config.RAZORPAY_KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(),
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def webhook_signature_ok(body: bytes, signature: str) -> bool:
    if not config.RAZORPAY_WEBHOOK_SECRET or not signature:
        return False
    expected = hmac.new(config.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---- Stripe -----------------------------------------------------------------------------------------
def _stripe(method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One Stripe API call (form-encoded). Tests replace this function."""
    try:
        r = httpx.request(method, STRIPE_API + path, data=data, timeout=20,
                          headers={"Authorization": f"Bearer {config.STRIPE_SECRET_KEY}"})
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Stripe unreachable: {e}")
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 300:
        raise HTTPException(status_code=502, detail=f"Stripe error: {(body.get('error') or {}).get('message', r.status_code)}")
    return body


def create_stripe_session(payment: Payment, description: str, email: str) -> Dict[str, str]:
    base = config.FRONTEND_URL.rstrip("/")
    data = {
        "mode": "payment",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": payment.currency.lower(),
        "line_items[0][price_data][unit_amount]": str(payment.amount_paise),
        "line_items[0][price_data][product_data][name]": description[:250],
        "client_reference_id": str(payment.id),
        "metadata[payment_id]": str(payment.id),
        "payment_intent_data[metadata][payment_id]": str(payment.id),
        "customer_email": email,
        "success_url": f"{base}/payments/return?pid={payment.id}&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}/payments/return?pid={payment.id}&cancelled=1",
    }
    s = _stripe("POST", "/checkout/sessions", data)
    return {"id": s["id"], "url": s["url"]}


def stripe_session_paid(payment: Payment, session: Dict[str, Any]) -> bool:
    return (session.get("payment_status") == "paid"
            and int(session.get("amount_total") or -1) == payment.amount_paise
            and (session.get("currency") or "").upper() == payment.currency)


def stripe_signature_ok(body: bytes, header: str, tolerance: int = 300) -> bool:
    """Verify Stripe-Signature: t=<ts>,v1=<hex hmac of "<ts>.<body>">."""
    if not config.STRIPE_WEBHOOK_SECRET or not header:
        return False
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    sigs = [v for k, v in (p.split("=", 1) for p in header.split(",") if "=" in p) if k == "v1"]
    try:
        ts = int(parts.get("t", "0"))
    except ValueError:
        return False
    if abs(time.time() - ts) > tolerance:
        return False
    expected = hmac.new(config.STRIPE_WEBHOOK_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in sigs)


def fulfil(db: Session, payment: Payment, provider_payment_id: Optional[str]) -> List[Dict[str, Any]]:
    """Mark paid and deliver what was bought. Safe to call more than once."""
    if payment.status == "paid":
        return []
    payment.status = "paid"
    payment.paid_at = utcnow()
    payment.provider_payment_id = provider_payment_id
    payment.error = None
    events: List[Dict[str, Any]] = []
    if payment.purpose == "subscription":
        subs.start_subscription(db, payment.client_id, payment.plan_type, months=payment.months,
                                payment_id=payment.id, commit=False)
        events.append({"type": "plan_activated", "plan": payment.plan_type, "user_ids": []})  # admins only
        from app.services.notify import notify
        events += notify(db, payment.user_id, "plan_activated", f"Your {payment.plan_type} plan is active",
                         f"Payment of {payment.amount_paise / 100:,.2f} {payment.currency} received for "
                         f"{payment.months} month(s). Thank you!", "/client/billing", commit=False)
    elif payment.purpose == "order":
        o = db.get(Order, payment.order_id)
        if o and o.status == "pending_payment":
            o.status, o.paid_at = "in_progress", utcnow()
            events.append({"type": "order_paid", "order_id": o.id, "title": o.title,
                           "user_ids": [o.consultant.user_id] if o.consultant and o.consultant.user_id else []})
            from app.services.notify import notify
            events += notify(db, o.consultant.user_id if o.consultant else None, "order_paid",
                             f"Order #{o.id} is paid — you can start", f"“{o.title}” has been paid. Start the work "
                             f"and deliver it from the order page.", f"/orders/{o.id}", commit=False)
    db.commit()
    if payment.purpose == "order" and payment.order_id:
        from app.services import payouts
        o = db.get(Order, payment.order_id)
        if o and o.status == "in_progress":
            payouts.on_order_paid(db, o)  # never raises; failures are recorded on the order
    return events


def mark_failed(db: Session, payment: Payment, reason: str):
    if payment.status == "created":
        payment.status = "failed"
        payment.error = reason[:500]
        db.commit()
