"""Freelancer payouts through Razorpay Route.

Money flow:
  1. Client pays the order (full amount) → platform's Razorpay account.
  2. On payment, the freelancer's share (amount − platform fee) is transferred from that payment to the
     freelancer's Route linked account with on_hold=true. Razorpay keeps it until we release it.
  3. Client approves the delivery → PATCH the transfer to on_hold=false → Razorpay settles it to the
     freelancer's bank / UPI on the linked account's settlement schedule.
If the freelancer hasn't added payout details yet, the transfer is created when they do. If Route is off or a
call fails, the order shows payout "pending"/"failed" and an admin can retry or pay out manually.

Modes: "razorpay" (keys + RAZORPAY_ROUTE_ENABLED), "demo" (simulated IDs, no money moves), "off" (manual).
"""
import re
import secrets
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core import config
from app.models import Consultant, Order, Payment
from app.models._time import utcnow

API = "https://api.razorpay.com"


class RouteError(Exception):
    pass


def mode() -> str:
    from app.services.payments import razorpay_on, demo_allowed
    if demo_allowed():
        return "demo"
    if razorpay_on() and config.RAZORPAY_ROUTE_ENABLED:
        return "razorpay"
    return "off"


INTL_REASON = "Automatic payouts (Razorpay Route) support INR orders only — pay this international order manually."


def _rzp(method: str, path: str, json: Optional[dict] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    """One Razorpay API call. Tests replace this function."""
    headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
    try:
        r = httpx.request(method, API + path, json=json, headers=headers,
                          auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET), timeout=20)
    except httpx.HTTPError as e:
        raise RouteError(f"Razorpay unreachable: {e}")
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 300:
        err = (data.get("error") or {}) if isinstance(data, dict) else {}
        if r.status_code == 403:
            raise RouteError("Route is not enabled on the Razorpay account. Ask Razorpay to activate Route.")
        raise RouteError(err.get("description") or f"Razorpay error {r.status_code}")
    return data


# ---- linked accounts ------------------------------------------------------------------------------
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
VPA_RE = re.compile(r"^[A-Za-z0-9.\-_]{2,256}@[A-Za-z][A-Za-z0-9.\-]{1,64}$")


def mask_account(number: str) -> str:
    return "••••" + number[-4:]


def setup_account(db: Session, c: Consultant, *, method: str, beneficiary_name: str, account_number: Optional[str],
                  ifsc: Optional[str], vpa: Optional[str], phone: Optional[str]) -> Consultant:
    """Create (or replace) the freelancer's Route linked account. Only a masked form is stored."""
    m = mode()
    if m == "off":
        raise HTTPException(status_code=400, detail="Automatic payouts aren't enabled on this platform yet. "
                                                    "An admin will pay you out manually after each approved order.")
    if method == "bank_account":
        settlement = {"method": "bank_account", "bank_account": {
            "account_number": account_number, "beneficiary_name": beneficiary_name, "code_type": "ifsc",
            "code": ifsc, "currency": "INR", "is_default": True}}
        masked = f"{ifsc} · {mask_account(account_number)}"
    else:
        settlement = {"method": "upi", "upi": {"vpa": vpa, "beneficiary_name": beneficiary_name,
                                               "currency": "INR", "is_default": True}}
        masked = vpa

    if m == "demo":
        account_id, status, note = "acc_demo_" + secrets.token_hex(6), "active", None
    else:
        body = {"type": "route", "tnc_accepted": True, "reference_id": f"tm_freelancer_{c.id}_{secrets.token_hex(4)}",
                "legal_business_name": beneficiary_name, "business_type": "individual", "email": c.email,
                "notes": {"talentmatch_consultant_id": str(c.id)}, "settlement_accounts": [settlement]}
        if phone:
            body["phone"] = phone
        try:
            data = _rzp("POST", "/v2/accounts", body, idempotency_key=str(uuid.uuid4()))
        except RouteError as e:
            raise HTTPException(status_code=400, detail=f"Razorpay couldn't set up payouts: {e}")
        account_id = data["id"]
        prod = data.get("product_config") or {}
        sa = ((prod.get("active_configuration") or {}).get("settlement_accounts") or [{}])[0]
        verified = sa.get("verification_status") in (None, "verified")
        if prod.get("activation_status") in (None, "activated") and verified:
            status, note = "active", None
        else:
            status, note = "under_review", "Razorpay is verifying your account (usually 10–15 minutes for bank accounts)."
    c.payout_account_id, c.payout_method, c.payout_masked = account_id, method, masked
    c.payout_beneficiary, c.payout_status, c.payout_note = beneficiary_name, status, note
    db.commit()
    return c


def can_receive(c: Optional[Consultant]) -> bool:
    return bool(c and c.payout_account_id and c.payout_status in ("active", "under_review"))


# ---- transfers ------------------------------------------------------------------------------------
def _order_payment(db: Session, o: Order) -> Optional[Payment]:
    return (db.query(Payment).filter(Payment.order_id == o.id, Payment.status == "paid")
            .order_by(Payment.id.desc()).first())


def _earnings(o: Order) -> int:
    return o.amount_paise - o.platform_fee_paise


def _create_transfer(db: Session, o: Order, on_hold: bool):
    c = o.consultant
    p = _order_payment(db, o)
    if not p or not p.provider_payment_id:
        raise RouteError("No captured payment found for this order")
    m = mode()
    if m == "demo":
        o.transfer_id, o.transfer_status = "trf_demo_" + secrets.token_hex(6), "processed"
    else:
        # Idempotent: reuse a transfer we already created for this order (e.g. after a crash before commit).
        existing = _rzp("GET", f"/v1/payments/{p.provider_payment_id}/transfers")
        for t in existing.get("items", []):
            if (t.get("notes") or {}).get("talentmatch_order_id") == str(o.id):
                o.transfer_id, o.transfer_status = t["id"], t.get("status")
                break
        else:
            data = _rzp("POST", f"/v1/payments/{p.provider_payment_id}/transfers", {"transfers": [{
                "account": c.payout_account_id, "amount": _earnings(o), "currency": "INR",
                "notes": {"talentmatch_order_id": str(o.id), "title": o.title[:200]},
                "linked_account_notes": ["talentmatch_order_id"], "on_hold": on_hold}]})
            t = data["items"][0]
            o.transfer_id, o.transfer_status = t["id"], t.get("status")
            if (t.get("error") or {}).get("description"):
                raise RouteError(t["error"]["description"])
    o.payout_mode = "demo" if m == "demo" else "route"


def _release_transfer(o: Order):
    if mode() == "razorpay" and not o.transfer_id.startswith("trf_demo_"):
        t = _rzp("PATCH", f"/v1/transfers/{o.transfer_id}", {"on_hold": False})
        o.transfer_status = t.get("status", o.transfer_status)


def on_order_paid(db: Session, o: Order) -> None:
    """Called after an order is paid: park the freelancer's share in their Route account, on hold."""
    if mode() == "off" or o.transfer_id or o.currency != "INR" or not can_receive(o.consultant):
        return
    try:
        _create_transfer(db, o, on_hold=True)
        o.payout_status, o.payout_error = "held", None
    except RouteError as e:
        o.payout_error = f"Transfer not created yet: {e}"  # retried on approval
    db.commit()


def release(db: Session, o: Order) -> Dict[str, Any]:
    """Called when the client approves (and by admin retry). Never raises; records the outcome on the order."""
    if o.status != "completed" or o.payout_status == "released":
        return {"ok": o.payout_status == "released"}
    m = mode()
    try:
        if o.currency != "INR":
            o.payout_status, o.payout_mode, o.payout_error = "pending", "manual", INTL_REASON
        elif m == "off":
            o.payout_status, o.payout_mode = "pending", "manual"
            o.payout_error = "Automatic payouts are off — pay the freelancer manually, then record it."
        elif not can_receive(o.consultant):
            o.payout_status = "pending"
            o.payout_error = "The freelancer hasn't added payout details yet. It will be paid automatically when they do."
        else:
            if o.transfer_id:
                _release_transfer(o)
            else:
                _create_transfer(db, o, on_hold=False)
            o.payout_status, o.payout_error, o.payout_released_at = "released", None, utcnow()
    except RouteError as e:
        o.payout_status, o.payout_error = "failed", str(e)[:500]
    db.commit()
    return {"ok": o.payout_status == "released", "status": o.payout_status, "error": o.payout_error}


def catch_up(db: Session, c: Consultant) -> List[int]:
    """After a freelancer adds payout details: park money for paid orders and pay approved ones."""
    done = []
    if not can_receive(c):
        return done
    for o in db.query(Order).filter(Order.consultant_id == c.id, Order.transfer_id.is_(None), Order.currency == "INR",
                                    Order.status.in_(("in_progress", "delivered", "completed")),
                                    Order.payout_status.in_(("none", "pending", "failed"))).all():
        if o.status == "completed":
            if release(db, o)["ok"]:
                done.append(o.id)
        else:
            on_order_paid(db, o)
    return done


# ---- webhooks -------------------------------------------------------------------------------------
def handle_webhook(db: Session, event: Dict[str, Any]) -> Optional[str]:
    kind = event.get("event", "")
    payload = event.get("payload") or {}
    if kind in ("transfer.processed", "transfer.failed"):
        t = (payload.get("transfer") or {}).get("entity") or {}
        o = db.query(Order).filter(Order.transfer_id == t.get("id")).first() if t.get("id") else None
        if not o:
            return "ignored"
        o.transfer_status = t.get("status") or kind.split(".")[1]
        if kind == "transfer.failed":
            o.payout_status = "failed"
            o.payout_error = ((t.get("error") or {}).get("description") or "Transfer failed")[:500]
        db.commit()
        return "ok"
    if kind.startswith("product.route.") or kind.startswith("account."):
        ent = (payload.get("merchant_product") or payload.get("account") or {}).get("entity") or {}
        acc = ent.get("merchant_id") or ent.get("id") or event.get("account_id")
        c = db.query(Consultant).filter(Consultant.payout_account_id == acc).first() if acc else None
        if not c:
            return "ignored"
        status = {"product.route.activated": "active", "account.activated": "active",
                  "product.route.under_review": "under_review", "account.under_review": "under_review",
                  "product.route.needs_clarification": "needs_clarification",
                  "account.needs_clarification": "needs_clarification"}.get(kind)
        if status:
            c.payout_status = status
            c.payout_note = None if status == "active" else \
                "Razorpay needs more information. Check your details and save them again."
            db.commit()
            if status == "active":
                catch_up(db, c)
        return "ok"
    return None
