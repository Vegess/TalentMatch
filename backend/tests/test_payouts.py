import hashlib
import hmac
import json

import pytest

from app.core import config
from app.services import payments as pay, payouts
from tests.conftest import API, signup, admin_headers, freelancer_with_skills, post_job, pay_demo

UPI = {"method": "upi", "beneficiary_name": "Kavya Reddy", "vpa": "kavya@okhdfcbank"}
BANK = {"method": "bank_account", "beneficiary_name": "Kavya Reddy", "account_number": "1234567890123456",
        "ifsc": "hdfc0000317"}


def _hired_order(client, pay_it=True):
    ch, _ = signup(client, "client", "c@x.in")
    fh, prof = freelancer_with_skills(client, "f@x.in", ["Python"], 4)
    job = post_job(client, ch, ["Python"]).json()
    pid = client.post(f"{API}/jobs/{job['id']}/proposals", headers=fh,
                      json={"cover_letter": "Happy to help with this project.", "bid_amount": 20000}).json()["id"]
    order = client.post(f"{API}/proposals/{pid}/accept", headers=ch).json()
    if pay_it:
        pay_demo(client, ch, purpose="order", order_id=order["id"])
    return ch, fh, order["id"]


def _deliver_and_approve(client, ch, fh, oid):
    client.post(f"{API}/orders/{oid}/deliver", headers=fh, json={"delivery_note": "All done, repo shared."})
    return client.post(f"{API}/orders/{oid}/complete", headers=ch).json()


# ---------------------------------------------------------------- demo mode (no keys)
def test_demo_route_hold_then_release(client):
    ch, fh, oid = _hired_order(client, pay_it=False)
    r = client.put(f"{API}/freelancers/me/payout", headers=fh, json=UPI)
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["mode"] == "demo"
    pay_demo(client, ch, purpose="order", order_id=oid)
    o = client.get(f"{API}/orders/{oid}", headers=fh).json()
    assert o["payout_status"] == "held" and o["transfer_id"].startswith("trf_demo_")
    done = _deliver_and_approve(client, ch, fh, oid)
    assert done["payout_status"] == "released" and done["payout_mode"] == "demo" and done["payout_released_at"]
    me = client.get(f"{API}/freelancers/me/payout", headers=fh).json()
    assert me["totals"]["released"] == 18000.0
    ov = client.get(f"{API}/admin/overview", headers=admin_headers(client)).json()
    assert ov["money"]["payouts_released"] == 18000.0 and ov["payout_mode"] == "demo"
    assert ov["freelancers_with_payouts"] == 1


def test_payout_waits_for_details_then_pays_automatically(client):
    ch, fh, oid = _hired_order(client)
    done = _deliver_and_approve(client, ch, fh, oid)
    assert done["payout_status"] == "pending" and "payout details" in done["payout_error"]
    r = client.put(f"{API}/freelancers/me/payout", headers=fh, json=BANK).json()
    assert r["orders_paid_now"] == [oid]
    o = client.get(f"{API}/orders/{oid}", headers=fh).json()
    assert o["payout_status"] == "released" and o["transfer_id"]


def test_details_added_mid_order_parks_money(client):
    ch, fh, oid = _hired_order(client)  # paid before details exist → nothing held yet
    assert client.get(f"{API}/orders/{oid}", headers=fh).json()["payout_status"] == "none"
    client.put(f"{API}/freelancers/me/payout", headers=fh, json=UPI)
    assert client.get(f"{API}/orders/{oid}", headers=fh).json()["payout_status"] == "held"


def test_payout_details_are_masked_and_validated(client):
    fh, _ = signup(client, "freelancer", "f@x.in")
    ch, _ = signup(client, "client", "c@x.in")
    r = client.put(f"{API}/freelancers/me/payout", headers=fh, json=BANK).json()
    assert r["masked"] == "HDFC0000317 · ••••3456" and r["method"] == "bank_account"
    blob = json.dumps(client.get(f"{API}/freelancers/me/payout", headers=fh).json())
    blob += json.dumps(client.get(f"{API}/freelancers/me", headers=fh).json())
    blob += json.dumps(client.get(f"{API}/admin/audit", headers=admin_headers(client)).json())
    assert "1234567890123456" not in blob
    bad = [{**BANK, "ifsc": "HDFC317"}, {**BANK, "account_number": "12"}, {**UPI, "vpa": "not-a-vpa"},
           {**UPI, "beneficiary_name": "Ab"}, {**UPI, "phone": "12ab"}]
    for b in bad:
        assert client.put(f"{API}/freelancers/me/payout", headers=fh, json=b).status_code == 422, b
    assert client.put(f"{API}/freelancers/me/payout", headers=ch, json=UPI).status_code == 403


# ---------------------------------------------------------------- real Razorpay (API mocked)
class FakeRzp:
    """Records Razorpay calls and answers like the Route API."""
    def __init__(self, fail_on=None):
        self.calls, self.fail_on, self.transfers = [], fail_on or set(), []

    def __call__(self, method, path, json=None, idempotency_key=None):
        self.calls.append((method, path, json, idempotency_key))
        key = f"{method} {path.split('/')[1] if path.startswith('/v2') else path.split('/')[2]}"
        if any(f in f"{method} {path}" for f in self.fail_on):
            raise payouts.RouteError("Bank rejected the transfer")
        if method == "POST" and path == "/v2/accounts":
            return {"id": "acc_TEST1", "status": "created", "product_config": {"activation_status": "activated",
                    "active_configuration": {"settlement_accounts": [{"verification_status": "pending"}]}}}
        if method == "GET" and path.endswith("/transfers"):
            return {"items": list(self.transfers)}
        if method == "POST" and path.endswith("/transfers"):
            t = {"id": "trf_TEST1", "status": "pending", "on_hold": json["transfers"][0]["on_hold"],
                 "notes": json["transfers"][0]["notes"]}
            self.transfers.append(t)
            return {"entity": "collection", "count": 1, "items": [t]}
        if method == "PATCH" and path.startswith("/v1/transfers/"):
            return {"id": path.rsplit("/", 1)[1], "status": "processed", "on_hold": False}
        raise AssertionError(f"unexpected call {key}")


@pytest.fixture()
def razorpay_route(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_123")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "s3cret")
    monkeypatch.setattr(config, "RAZORPAY_WEBHOOK_SECRET", "whsec")
    monkeypatch.setattr(config, "RAZORPAY_ROUTE_ENABLED", True)
    fake = FakeRzp()
    monkeypatch.setattr(payouts, "_rzp", fake)
    counter = iter(range(1, 100))
    monkeypatch.setattr(pay, "create_provider_order", lambda amount, receipt, notes: f"order_T{next(counter)}")
    return fake


def _sig(secret, msg: bytes):
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def _pay_razorpay(client, ch, oid):
    co = client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "order", "order_id": oid}).json()
    body = {"payment_id": co["payment_id"], "razorpay_order_id": co["provider_order_id"],
            "razorpay_payment_id": "pay_REAL1",
            "razorpay_signature": _sig("s3cret", f"{co['provider_order_id']}|pay_REAL1".encode())}
    r = client.post(f"{API}/payments/verify", headers=ch, json=body)
    assert r.status_code == 200, r.text


def test_razorpay_route_full_flow(client, razorpay_route):
    fake = razorpay_route
    ch, fh, oid = _hired_order(client, pay_it=False)
    r = client.put(f"{API}/freelancers/me/payout", headers=fh, json=BANK).json()
    assert r["status"] == "under_review" and r["account_id"] == "acc_TEST1"   # bank penny-drop pending
    _, path, body, idem = fake.calls[0]
    assert path == "/v2/accounts" and idem and body["type"] == "route" and body["tnc_accepted"] is True
    assert body["business_type"] == "individual" and body["settlement_accounts"][0]["bank_account"]["code"] == "HDFC0000317"

    _pay_razorpay(client, ch, oid)
    post = [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/transfers")][0]
    assert post[1] == "/v1/payments/pay_REAL1/transfers"
    t = post[2]["transfers"][0]
    assert t == {**t, "account": "acc_TEST1", "amount": 1800000, "currency": "INR", "on_hold": True}
    assert client.get(f"{API}/orders/{oid}", headers=fh).json()["payout_status"] == "held"

    done = _deliver_and_approve(client, ch, fh, oid)
    assert done["payout_status"] == "released" and done["transfer_status"] == "processed"
    assert ("PATCH", "/v1/transfers/trf_TEST1", {"on_hold": False}, None) in fake.calls


def test_route_failure_does_not_break_payment_and_admin_can_retry(client, razorpay_route):
    fake = razorpay_route
    ch, fh, oid = _hired_order(client, pay_it=False)
    client.put(f"{API}/freelancers/me/payout", headers=fh, json=UPI)
    fake.fail_on = {"POST /v1/payments/pay_REAL1/transfers"}
    _pay_razorpay(client, ch, oid)  # payment still succeeds
    o = client.get(f"{API}/orders/{oid}", headers=ch).json()
    assert o["status"] == "in_progress" and o["payout_status"] == "none" and "Bank rejected" in o["payout_error"]
    done = _deliver_and_approve(client, ch, fh, oid)
    assert done["status"] == "completed" and done["payout_status"] == "failed"
    ah = admin_headers(client)
    assert client.post(f"{API}/admin/orders/{oid}/retry-payout", headers=ah).status_code == 400
    fake.fail_on = set()
    r = client.post(f"{API}/admin/orders/{oid}/retry-payout", headers=ah)
    assert r.status_code == 200 and r.json()["payout_status"] == "released"
    # a transfer for this order is never created twice
    creates = [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/transfers")]
    assert len(fake.transfers) == 1 and len(creates) == 4  # at payment, at approval, failed retry, successful retry


def test_retry_reuses_existing_transfer(client, razorpay_route):
    fake = razorpay_route
    ch, fh, oid = _hired_order(client, pay_it=False)
    client.put(f"{API}/freelancers/me/payout", headers=fh, json=UPI)
    _pay_razorpay(client, ch, oid)
    from app.core.database import SessionLocal
    from app.models import Order
    db = SessionLocal()
    o = db.get(Order, oid)
    o.transfer_id = None  # simulate a crash after Razorpay created the transfer but before we saved it
    db.commit()
    db.close()
    _deliver_and_approve(client, ch, fh, oid)
    assert len(fake.transfers) == 1  # found by notes.talentmatch_order_id instead of creating another


def test_route_webhooks(client, razorpay_route):
    ch, fh, oid = _hired_order(client, pay_it=False)
    client.put(f"{API}/freelancers/me/payout", headers=fh, json=BANK)

    def send(event):
        body = json.dumps(event).encode()
        return client.post(f"{API}/payments/webhook", content=body,
                           headers={"x-razorpay-signature": _sig("whsec", body), "content-type": "application/json"})

    assert send({"event": "product.route.activated", "account_id": "acc_TEST1",
                 "payload": {"merchant_product": {"entity": {"merchant_id": "acc_TEST1"}}}}).json()["status"] == "ok"
    assert client.get(f"{API}/freelancers/me/payout", headers=fh).json()["status"] == "active"
    _pay_razorpay(client, ch, oid)
    r = send({"event": "transfer.failed", "payload": {"transfer": {"entity": {
        "id": "trf_TEST1", "status": "failed", "error": {"description": "Beneficiary bank down"}}}}})
    assert r.json()["status"] == "ok"
    o = client.get(f"{API}/orders/{oid}", headers=fh).json()
    assert o["payout_status"] == "failed" and o["payout_error"] == "Beneficiary bank down"
    assert send({"event": "transfer.processed", "payload": {"transfer": {"entity": {"id": "trf_UNKNOWN"}}}}).json()["status"] == "ignored"


def test_route_off_falls_back_to_manual(client, monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setattr(config, "RAZORPAY_ROUTE_ENABLED", False)
    fh, _ = signup(client, "freelancer", "f@x.in")
    r = client.put(f"{API}/freelancers/me/payout", headers=fh, json=UPI)
    assert r.status_code == 400 and "manually" in r.json()["detail"]
    assert client.get(f"{API}/freelancers/me/payout", headers=fh).json()["mode"] == "off"


def test_manual_release_only_when_waiting(client):
    ch, fh, oid = _hired_order(client)
    client.put(f"{API}/freelancers/me/payout", headers=fh, json=UPI)
    done = _deliver_and_approve(client, ch, fh, oid)
    assert done["payout_status"] == "released"
    ah = admin_headers(client)
    assert client.post(f"{API}/admin/orders/{oid}/release-payout", headers=ah).status_code == 400  # already paid
    assert client.post(f"{API}/admin/orders/{oid}/retry-payout", headers=ah).status_code == 400
    assert client.post(f"{API}/admin/orders/{oid}/retry-payout", headers=fh).status_code == 403
