import hashlib
import hmac
import json
import time

import pytest

from app.core import config
from app.services import payments as pay, email
from tests.conftest import API, PASSWORD, signup, login, admin_headers, freelancer_with_skills, post_job, pay_demo


def _completed_order(client, client_email="c@x.in", f_email="f@x.in"):
    ch, cu = signup(client, "client", client_email, company="Acme")
    fh, prof = freelancer_with_skills(client, f_email, ["Python"], 4)
    job = post_job(client, ch, ["Python"]).json()
    pid = client.post(f"{API}/jobs/{job['id']}/proposals", headers=fh,
                      json={"cover_letter": "Happy to help with this project.", "bid_amount": 20000}).json()["id"]
    oid = client.post(f"{API}/proposals/{pid}/accept", headers=ch).json()["id"]
    pay_demo(client, ch, purpose="order", order_id=oid)
    client.post(f"{API}/orders/{oid}/deliver", headers=fh, json={"delivery_note": "All done, repo shared."})
    client.post(f"{API}/orders/{oid}/complete", headers=ch)
    return ch, cu, fh, prof, oid, job


# ----------------------------------------------------------------- reviews & badges
def test_reviews_both_sides_and_ratings(client):
    ch, cu, fh, prof, oid, _ = _completed_order(client)
    assert client.get(f"{API}/reviews/order/{oid}", headers=ch).json()["can_review"] is True
    r = client.post(f"{API}/reviews", headers=ch, json={"order_id": oid, "rating": 5, "comment": "Superb work"})
    assert r.status_code == 200 and r.json()["reviewer_name"] == "Acme"
    assert client.post(f"{API}/reviews", headers=ch, json={"order_id": oid, "rating": 4}).status_code == 400
    assert client.post(f"{API}/reviews", headers=fh, json={"order_id": oid, "rating": 4}).status_code == 200
    assert client.post(f"{API}/reviews", headers=fh, json={"order_id": oid, "rating": 9}).status_code == 422
    pub = client.get(f"{API}/reviews/freelancer/{prof['id']}").json()
    assert pub["rating_avg"] == 5.0 and pub["rating_count"] == 1 and pub["distribution"]["5"] == 1
    assert client.get(f"{API}/freelancers/{prof['id']}").json()["rating_count"] == 1
    assert client.get(f"{API}/reviews/client/{cu['client_id']}", headers=fh).json()["rating_avg"] == 4.0
    other, _ = signup(client, "client", "o@x.in")
    assert client.post(f"{API}/reviews", headers=other, json={"order_id": oid, "rating": 1}).status_code == 404
    kinds = [n["kind"] for n in client.get(f"{API}/notifications", headers=fh).json()["items"]]
    assert "review" in kinds and "approved" in kinds and "order_paid" in kinds and "hired" in kinds


def test_review_only_after_completion(client):
    ch, _ = signup(client, "client", "c@x.in")
    fh, _ = signup(client, "freelancer", "f@x.in")
    s = client.post(f"{API}/services", headers=fh, json={"title": "Write a pitch deck", "price": 3000}).json()
    o = client.post(f"{API}/services/{s['id']}/order", headers=ch, json={}).json()
    assert client.post(f"{API}/reviews", headers=ch, json={"order_id": o["id"], "rating": 5}).status_code == 400


def test_admin_verification_badge(client):
    fh, fu = signup(client, "freelancer", "f@x.in")
    ah = admin_headers(client)
    r = client.patch(f"{API}/admin/users/{fu['id']}", headers=ah, json={"verified": True})
    assert r.status_code == 200 and r.json()["verified"] is True
    assert "verified" in client.get(f"{API}/freelancers/me", headers=fh).json()["badges"]
    assert client.get(f"{API}/freelancers?verified=true").json()["total"] == 1
    assert client.patch(f"{API}/admin/users/{fu['id']}", headers=fh, json={"verified": True}).status_code == 403


# ----------------------------------------------------------------- messages
def test_messaging_rules_and_flow(client):
    ch, cu = signup(client, "client", "c@x.in", company="Acme")
    fh, prof = freelancer_with_skills(client, "f@x.in", ["Python"], 3)
    stranger_h, stranger = signup(client, "freelancer", "s@x.in")
    # FREE client → can't cold-message; freelancer can't message a client they never applied to
    r = client.post(f"{API}/conversations", headers=ch, json={"consultant_id": prof["id"], "body": "Hi"})
    assert r.status_code == 403 and "Free plan" in r.json()["detail"]
    assert client.post(f"{API}/conversations", headers=fh, json={"client_id": cu["client_id"]}).status_code == 403
    job = post_job(client, ch, ["Python"]).json()
    client.post(f"{API}/jobs/{job['id']}/proposals", headers=fh, json={"cover_letter": "Twenty characters at least.", "bid_amount": 500})
    conv = client.post(f"{API}/conversations", headers=ch, json={"consultant_id": prof["id"], "job_id": job["id"],
                                                                 "body": "Can you start Monday?"}).json()
    assert conv["other"]["name"] == prof["name"] and conv["job"]["id"] == job["id"]
    inbox = client.get(f"{API}/conversations", headers=fh).json()
    assert inbox[0]["unread"] == 1 and inbox[0]["other"]["name"] == "Acme"
    assert client.get(f"{API}/conversations/unread-count", headers=fh).json()["unread"] == 1
    thread = client.get(f"{API}/conversations/{conv['id']}", headers=fh).json()
    assert [m["body"] for m in thread["messages"]] == ["Can you start Monday?"] and thread["messages"][0]["mine"] is False
    assert client.get(f"{API}/conversations/unread-count", headers=fh).json()["unread"] == 0
    assert client.post(f"{API}/conversations/{conv['id']}/messages", headers=fh, json={"body": "Yes!"}).json()["mine"] is True
    assert client.get(f"{API}/conversations/{conv['id']}", headers=stranger_h).status_code == 404
    assert client.post(f"{API}/conversations/{conv['id']}/messages", headers=stranger_h, json={"body": "spam"}).status_code == 404
    # same pair → same conversation
    again = client.post(f"{API}/conversations", headers=fh, json={"client_id": cu["client_id"]}).json()
    assert again["id"] == conv["id"]
    # paid plan → can message anyone
    pay_demo(client, ch, purpose="subscription", plan_type="PREMIUM")
    assert client.post(f"{API}/conversations", headers=ch, json={"consultant_id": stranger["consultant_id"]}).status_code == 200


def test_message_notifications_email_once_and_realtime(client):
    ch, cu = signup(client, "client", "c@x.in", company="Acme")
    fh, fu = signup(client, "freelancer", "f@x.in")
    pay_demo(client, ch, purpose="subscription", plan_type="PREMIUM")
    email.sent_log.clear()
    token = fh["Authorization"].split()[1]
    with client.websocket_connect(f"/ws?token={token}") as ws:
        conv = client.post(f"{API}/conversations", headers=ch, json={"consultant_id": fu["consultant_id"], "body": "Hello"}).json()
        got = [ws.receive_json(), ws.receive_json()]
        assert {g["type"] for g in got} == {"message", "notification"}
    client.post(f"{API}/conversations/{conv['id']}/messages", headers=ch, json={"body": "Second message"})
    to_f = [m for m in email.sent_log if m["to"] == "f@x.in"]
    assert len(to_f) == 1 and "New message from Acme" in to_f[0]["subject"]
    client.patch(f"{API}/auth/me", headers=fh, json={"email_notifications": False})
    client.get(f"{API}/conversations/{conv['id']}", headers=fh)  # read → next message is "first unread" again
    client.post(f"{API}/conversations/{conv['id']}/messages", headers=ch, json={"body": "Third"})
    assert len([m for m in email.sent_log if m["to"] == "f@x.in"]) == 1  # opted out
    n = client.get(f"{API}/notifications", headers=fh).json()
    assert n["unread"] == 3
    assert client.post(f"{API}/notifications/read-all", headers=fh).json()["marked"] == 3
    assert client.post(f"{API}/notifications/{n['items'][0]['id']}/read", headers=ch).status_code == 404


# ----------------------------------------------------------------- password reset & preferences
def test_password_reset_flow(client):
    signup(client, "client", "c@x.in")
    login(client, "c@x.in", PASSWORD)
    email.sent_log.clear()
    a = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@x.in"}).json()
    b = client.post(f"{API}/auth/forgot-password", json={"email": "C@x.in"}).json()
    assert a == b  # no account enumeration
    assert len(email.sent_log) == 1
    token = email.sent_log[0]["text"].split("reset-password?token=")[1].split()[0]
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "short"}).status_code == 422
    r = client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "Brand#New2026"})
    assert r.status_code == 200 and r.json()["access_token"]
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "Again#New2026"}).status_code == 400
    login(client, "c@x.in", "Brand#New2026")
    assert client.post(f"{API}/auth/login", json={"email": "c@x.in", "password": PASSWORD}).status_code == 401
    # an older link stops working once a newer one is issued
    client.post(f"{API}/auth/forgot-password", json={"email": "c@x.in"})
    client.post(f"{API}/auth/forgot-password", json={"email": "c@x.in"})
    first, second = [m["text"].split("token=")[1].split()[0] for m in email.sent_log[-2:]]
    assert client.post(f"{API}/auth/reset-password", json={"token": first, "new_password": "Third#Pass2026"}).status_code == 400
    assert client.post(f"{API}/auth/reset-password", json={"token": second, "new_password": "Third#Pass2026"}).status_code == 200


def test_preferences(client):
    h, _ = signup(client, "freelancer", "f@x.in")
    r = client.patch(f"{API}/auth/me", headers=h, json={"preferred_language": "hi"}).json()
    assert r["preferred_language"] == "hi" and r["email_notifications"] is True
    assert client.patch(f"{API}/auth/me", headers=h, json={"preferred_language": "xx"}).status_code == 422


# ----------------------------------------------------------------- countries, timezones, currency
def _reg(client, role, email_, country=None, tz=None):
    r = client.post(f"{API}/auth/register", json={"role": role, "name": email_.split("@")[0], "email": email_,
                                                  "password": PASSWORD, "country": country, "timezone": tz})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


def test_geo_profile_and_filters(client):
    h1, _ = _reg(client, "freelancer", "a@x.in", "IN", "Asia/Kolkata")
    h2, _ = _reg(client, "freelancer", "b@x.in", "GB", "Europe/London")
    h3, _ = _reg(client, "freelancer", "c@x.in", "US", "America/New_York")
    client.put(f"{API}/freelancers/me", headers=h2, json={"languages": "English, Spanish", "work_start_hour": 9,
                                                         "work_end_hour": 17})
    assert client.put(f"{API}/freelancers/me", headers=h1, json={"timezone": "Moon/Base"}).status_code == 422
    assert client.put(f"{API}/freelancers/me", headers=h1, json={"country": "ZZ"}).status_code == 422
    assert client.get(f"{API}/freelancers?country=gb").json()["total"] == 1
    assert [f["country"] for f in client.get(f"{API}/freelancers?region=americas").json()["items"]] == ["US"]
    assert client.get(f"{API}/freelancers?language=spanish").json()["items"][0]["work_start_hour"] == 9
    me = client.get(f"{API}/freelancers/me", headers=h2).json()
    assert me["currency"] == "GBP" and me["region"] == "europe"


def test_currency_defaults_and_international_order(client):
    ch, cu = _reg(client, "client", "us@x.in", "US", "America/Chicago")
    assert cu["currency"] == "USD"
    p = pay_demo(client, ch, purpose="subscription", plan_type="PREMIUM", months=2)
    assert p["amount"] == 30.0 and p["currency"] == "USD"
    job = post_job(client, ch, ["Python"]).json()
    assert job["currency"] == "USD"
    fh, fu = _reg(client, "freelancer", "de@x.in", "DE", "Europe/Berlin")
    client.put(f"{API}/freelancers/me/payout", headers=fh, json={"method": "upi", "beneficiary_name": "Hans Meyer",
                                                               "vpa": "hans@okaxis"})
    s = client.post(f"{API}/services", headers=fh, json={"title": "Landing page design", "price": 400}).json()
    assert s["currency"] == "EUR"
    o = client.post(f"{API}/services/{s['id']}/order", headers=ch, json={}).json()
    assert o["currency"] == "EUR" and o["amount"] == 400.0
    pay_demo(client, ch, purpose="order", order_id=o["id"])
    client.post(f"{API}/orders/{o['id']}/deliver", headers=fh, json={"delivery_note": "Figma + HTML delivered."})
    done = client.post(f"{API}/orders/{o['id']}/complete", headers=ch).json()
    assert done["payout_status"] == "pending" and "INR orders only" in done["payout_error"]
    ov = client.get(f"{API}/admin/overview", headers=admin_headers(client)).json()
    assert ov["money_by_currency"]["USD"]["subscription_revenue"] == 30.0
    assert ov["money_by_currency"]["EUR"]["order_gmv"] == 400.0 and ov["money_by_currency"]["EUR"]["payouts_pending"] == 360.0
    assert ov["money"]["total_collected"] == 0  # INR card isn't polluted by other currencies
    assert ov["money_by_currency"]["USD"]["mrr"] == 15 and set(ov["currencies_in_use"]) >= {"INR", "USD", "EUR"}
    assert ov["countries"]["US"] == 1


# ----------------------------------------------------------------- Stripe
class FakeStripe:
    def __init__(self):
        self.calls, self.sessions = [], {}

    def __call__(self, method, path, data=None):
        self.calls.append((method, path, data))
        if method == "POST" and path == "/checkout/sessions":
            sid = f"cs_test_{len(self.sessions) + 1}"
            self.sessions[sid] = {"id": sid, "url": f"https://checkout.stripe.com/c/pay/{sid}", "payment_status": "unpaid",
                                  "amount_total": int(data["line_items[0][price_data][unit_amount]"]),
                                  "currency": data["line_items[0][price_data][currency]"], "payment_intent": f"pi_{sid}"}
            return self.sessions[sid]
        if method == "GET" and path.startswith("/checkout/sessions/"):
            return self.sessions[path.rsplit("/", 1)[1]]
        raise AssertionError(path)


@pytest.fixture()
def stripe(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "whsec_s")
    fake = FakeStripe()
    monkeypatch.setattr(pay, "_stripe", fake)
    return fake


def _stripe_sig(body: bytes, ts=None):
    ts = ts or int(time.time())
    return f"t={ts},v1=" + hmac.new(b"whsec_s", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


def test_stripe_checkout_confirm(client, stripe):
    ch, cu = _reg(client, "client", "us@x.in", "US", "America/Chicago")
    co = client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "subscription", "plan_type": "ENTERPRISE"}).json()
    assert co["provider"] == "stripe" and co["checkout_url"].startswith("https://checkout.stripe.com/")
    _, _, data = stripe.calls[0]
    assert data["line_items[0][price_data][currency]"] == "usd" and data["line_items[0][price_data][unit_amount]"] == "5900"
    assert "{CHECKOUT_SESSION_ID}" in data["success_url"] and data["metadata[payment_id]"] == str(co["payment_id"])
    assert client.post(f"{API}/payments/{co['payment_id']}/demo-complete", headers=ch, json={}).status_code == 400
    body = {"payment_id": co["payment_id"], "session_id": co["provider_order_id"]}
    assert client.post(f"{API}/payments/stripe/confirm", headers=ch, json=body).json()["status"] == "created"  # unpaid
    stripe.sessions[co["provider_order_id"]]["payment_status"] = "paid"
    assert client.post(f"{API}/payments/stripe/confirm", headers=ch, json=body).json()["status"] == "paid"
    me = client.get(f"{API}/subscriptions/me", headers=ch).json()
    assert me["active"]["plan_type"] == "ENTERPRISE"
    other, _ = signup(client, "client", "o@x.in")
    assert client.post(f"{API}/payments/stripe/confirm", headers=other, json=body).status_code == 404


def test_stripe_amount_mismatch_and_webhook(client, stripe):
    ch, _ = _reg(client, "client", "gb@x.in", "GB", "Europe/London")
    co = client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "subscription", "plan_type": "PREMIUM"}).json()
    assert co["currency"] == "GBP" and co["amount_minor"] == 1200
    sess = {**stripe.sessions[co["provider_order_id"]], "payment_status": "paid", "amount_total": 100}

    def send(event, sig=None):
        raw = json.dumps(event).encode()
        return client.post(f"{API}/payments/stripe/webhook", content=raw,
                           headers={"stripe-signature": sig or _stripe_sig(raw), "content-type": "application/json"})

    ev = {"type": "checkout.session.completed", "data": {"object": sess}}
    assert send(ev, sig="t=1,v1=bad").status_code == 400
    raw = json.dumps(ev).encode()
    assert send(ev, sig=_stripe_sig(raw, ts=int(time.time()) - 3600)).status_code == 400  # replayed / stale
    assert send(ev).json()["status"] == "amount_mismatch"
    ev["data"]["object"]["amount_total"] = 1200
    assert send(ev).json()["status"] == "ok"
    assert send(ev).json()["status"] == "ok"  # duplicate delivery is harmless
    me = client.get(f"{API}/subscriptions/me", headers=ch).json()
    assert me["active"]["plan_type"] == "PREMIUM" and len(me["history"]) == 2


def test_provider_routing(client, stripe, monkeypatch):
    # Stripe only → INR also goes through Stripe; demo is off
    ch, _ = signup(client, "client", "in@x.in")
    assert client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "subscription", "plan_type": "PREMIUM"}).json()["provider"] == "stripe"
    # Razorpay only → INR via Razorpay, USD refused (never silently simulated)
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(config, "PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setattr(pay, "create_provider_order", lambda a, r, n: "order_X1")
    assert client.post(f"{API}/payments/checkout", headers=ch, json={"purpose": "subscription", "plan_type": "PREMIUM"}).json()["provider"] == "razorpay"
    uh, _ = _reg(client, "client", "us@x.in", "US", None)
    r = client.post(f"{API}/payments/checkout", headers=uh, json={"purpose": "subscription", "plan_type": "PREMIUM"})
    assert r.status_code == 400 and "USD" in r.json()["detail"]
    assert client.get(f"{API}/payments/config").json()["providers"] == {"INR": "razorpay", "USD": None, "EUR": None, "GBP": None}
