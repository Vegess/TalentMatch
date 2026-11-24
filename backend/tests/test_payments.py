import hashlib
import hmac
import json

from app.core import config
from app.services import payments as pay
from tests.conftest import API, signup, admin_headers, freelancer_with_skills, post_job, pay_demo


def _hire(client):
    ch, _ = signup(client, "client", "c@x.in")
    fh, _ = freelancer_with_skills(client, "f@x.in", ["Python"], 4)
    job = post_job(client, ch, ["Python"]).json()
    pid = client.post(f"{API}/jobs/{job['id']}/proposals", headers=fh,
                      json={"cover_letter": "Happy to help with this project.", "bid_amount": 20000}).json()["id"]
    order = client.post(f"{API}/proposals/{pid}/accept", headers=ch).json()
    return ch, fh, order


def test_plan_upgrade_with_demo_payment(client):
    ch, _ = signup(client, "client", "c@x.in")
    assert client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "subscription", "plan_type": "FREE"}).status_code == 400
    p = pay_demo(client, ch, purpose="subscription", plan_type="premium", months=3)
    assert p["status"] == "paid" and p["amount"] == 2997.0
    me = client.get(f"{API}/subscriptions/me", headers=ch).json()
    assert me["active"]["plan_type"] == "PREMIUM" and me["active"]["end_date"] and me["active"]["payment_id"] == p["id"]
    # idempotent: completing again doesn't create a second subscription
    client.post(f"{API}/payments/{p['id']}/demo-complete", headers=ch, json={"outcome": "success"})
    assert len(client.get(f"{API}/subscriptions/me", headers=ch).json()["history"]) == 2
    assert client.post(f"{API}/subscriptions/downgrade", headers=ch).json()["plan_type"] == "FREE"


def test_failed_payment_changes_nothing(client):
    ch, _ = signup(client, "client", "c@x.in")
    r = client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "subscription", "plan_type": "ENTERPRISE"}).json()
    p = client.post(f"{API}/payments/{r['payment_id']}/demo-complete", headers=ch, json={"outcome": "failure"}).json()
    assert p["status"] == "failed"
    assert client.get(f"{API}/subscriptions/me", headers=ch).json()["active"]["plan_type"] == "FREE"


def test_full_order_lifecycle_and_payout(client):
    ch, fh, order = _hire(client)
    oid = order["id"]
    assert client.post(f"{API}/orders/{oid}/deliver", headers=fh, json={"delivery_note": "Done early"}).status_code == 400
    pay_demo(client, ch, purpose="order", order_id=oid)
    assert client.get(f"{API}/orders/{oid}", headers=fh).json()["status"] == "in_progress"
    assert client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "order", "order_id": oid}).status_code == 400
    assert client.post(f"{API}/orders/{oid}/cancel", headers=ch).status_code == 400  # paid → no self-cancel
    assert client.post(f"{API}/orders/{oid}/complete", headers=ch).status_code == 400
    assert client.post(f"{API}/orders/{oid}/deliver", headers=ch, json={"delivery_note": "nope nope"}).status_code == 403
    assert client.post(f"{API}/orders/{oid}/deliver", headers=fh, json={"delivery_note": "Repo link + docs"}).json()["status"] == "delivered"
    assert client.post(f"{API}/orders/{oid}/request-changes", headers=ch).json()["status"] == "in_progress"
    client.post(f"{API}/orders/{oid}/deliver", headers=fh, json={"delivery_note": "Fixed the review comments"})
    done = client.post(f"{API}/orders/{oid}/complete", headers=ch).json()
    assert done["status"] == "completed" and done["payout_status"] == "pending" and done["freelancer_earnings"] == 18000.0
    ah = admin_headers(client)
    ov = client.get(f"{API}/admin/overview", headers=ah).json()
    assert ov["money"]["order_gmv"] == 20000.0 and ov["money"]["platform_fees"] == 2000.0
    assert ov["money"]["payouts_pending"] == 18000.0
    assert client.post(f"{API}/admin/orders/{oid}/release-payout", headers=ah).json()["payout_status"] == "released"
    assert client.post(f"{API}/admin/orders/{oid}/release-payout", headers=ah).status_code == 400
    actions = [a["action"] for a in client.get(f"{API}/admin/audit", headers=ah).json()]
    assert "payout.release" in actions and "order.complete" in actions and "payment.paid" in actions


def test_service_purchase(client):
    fh, _ = signup(client, "freelancer", "f@x.in")
    s = client.post(f"{API}/services", headers=fh, json={"title": "Logo and brand kit", "price": 5000, "delivery_days": 5}).json()
    ch, _ = signup(client, "client", "c@x.in")
    o = client.post(f"{API}/services/{s['id']}/order", headers=ch, json={"requirements": "Minimal, blue"}).json()
    assert o["amount"] == 5000.0 and o["status"] == "pending_payment"
    assert client.get(f"{API}/orders", headers=fh).json()[0]["id"] == o["id"]
    assert client.post(f"{API}/services/{s['id']}/order", headers=fh, json={}).status_code == 403


def test_cannot_pay_or_see_another_clients_order(client):
    ch, fh, order = _hire(client)
    other, _ = signup(client, "client", "o@x.in")
    assert client.post(f"{API}/payments/checkout", headers=other, json={"purpose": "order", "order_id": order["id"]}).status_code == 404
    assert client.get(f"{API}/orders/{order['id']}", headers=other).status_code == 404
    r = client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "order", "order_id": order["id"]}).json()
    assert client.post(f"{API}/payments/{r['payment_id']}/demo-complete", headers=other, json={}).status_code == 404


def _sig(secret, msg: bytes):
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def test_razorpay_verify_signature(client, monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_123")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "s3cret")
    monkeypatch.setattr(pay, "create_provider_order", lambda amount, receipt, notes: "order_TEST123")
    ch, _ = signup(client, "client", "c@x.in")
    co = client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "subscription", "plan_type": "PREMIUM"}).json()
    assert co["provider"] == "razorpay" and co["key_id"] == "rzp_test_123" and co["amount_paise"] == 99900
    # demo shortcut is refused when Razorpay is active
    assert client.post(f"{API}/payments/{co['payment_id']}/demo-complete", headers=ch, json={}).status_code == 400
    bad = {"payment_id": co["payment_id"], "razorpay_order_id": "order_TEST123", "razorpay_payment_id": "pay_1",
           "razorpay_signature": "0" * 64}
    assert client.post(f"{API}/payments/verify", headers=ch, json=bad).status_code == 400
    good = {**bad, "razorpay_signature": _sig("s3cret", b"order_TEST123|pay_1")}
    r = client.post(f"{API}/payments/verify", headers=ch, json=good)
    assert r.status_code == 200 and r.json()["status"] == "paid"
    assert client.get(f"{API}/subscriptions/me", headers=ch).json()["active"]["plan_type"] == "PREMIUM"


def test_razorpay_webhook(client, monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_123")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "s3cret")
    monkeypatch.setattr(config, "RAZORPAY_WEBHOOK_SECRET", "whsec")
    monkeypatch.setattr(pay, "create_provider_order", lambda amount, receipt, notes: "order_WH1")
    ch, _ = signup(client, "client", "c@x.in")
    co = client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "subscription", "plan_type": "ENTERPRISE"}).json()

    def send(event, amount):
        body = json.dumps({"event": event, "payload": {"payment": {"entity": {
            "id": "pay_WH", "order_id": "order_WH1", "amount": amount}}}}).encode()
        return client.post(f"{API}/payments/webhook", content=body,
                           headers={"x-razorpay-signature": _sig("whsec", body), "content-type": "application/json"})

    body = b'{"event":"payment.captured"}'
    assert client.post(f"{API}/payments/webhook", content=body, headers={"x-razorpay-signature": "bad"}).status_code == 400
    assert send("payment.captured", 1).json()["status"] == "amount_mismatch"
    assert send("payment.captured", 499900).json()["status"] == "ok"
    assert send("order.paid", 499900).json()["status"] == "ok"  # duplicate delivery is harmless
    me = client.get(f"{API}/subscriptions/me", headers=ch).json()
    assert me["active"]["plan_type"] == "ENTERPRISE" and len(me["history"]) == 2


def test_admin_grant_and_expiry(client):
    ch, cu = signup(client, "client", "c@x.in")
    ah = admin_headers(client)
    r = client.post(f"{API}/subscriptions/grant", headers=ah, json={"client_id": cu["client_id"], "plan_type": "ENTERPRISE"})
    assert r.json()["plan_type"] == "ENTERPRISE"
    assert client.post(f"{API}/subscriptions/grant", headers=ch, json={"client_id": cu["client_id"], "plan_type": "ENTERPRISE"}).status_code == 403
    from app.core.database import SessionLocal
    from app.services import subscriptions as subs
    import datetime as dt
    db = SessionLocal()
    subs.start_subscription(db, cu["client_id"], "PREMIUM", start_date=dt.datetime(2020, 1, 1), months=1)
    db.close()
    assert client.get(f"{API}/subscriptions/me", headers=ch).json()["active"] is None
    assert post_job(client, ch, ["A"]).status_code == 403
