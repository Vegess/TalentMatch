from tests.conftest import API, signup, admin_headers, make_pdf, freelancer_with_skills, post_job, pay_demo


def test_job_attachments_files_and_links(client):
    ch, _ = signup(client, "client", "c@x.in")
    other, _ = signup(client, "client", "o@x.in")
    fh, _ = signup(client, "freelancer", "f@x.in")
    job = post_job(client, ch, ["A"]).json()
    pdf = make_pdf(["Full job description", "Scope of work"])
    up = client.post(f"{API}/documents/upload", headers=ch, data={"owner_type": "job", "owner_id": job["id"], "title": "JD"},
                     files={"file": ("jd.pdf", pdf, "application/pdf")})
    assert up.status_code == 200 and up.json()["size_bytes"] == len(pdf)
    ln = client.post(f"{API}/documents/link", headers=ch, json={"owner_type": "job", "owner_id": job["id"],
                                                               "title": "Figma", "url": "https://figma.com/file/abc"})
    assert ln.status_code == 200
    assert client.post(f"{API}/documents/link", headers=ch, json={"owner_type": "job", "owner_id": job["id"],
                                                                 "title": "x", "url": "ftp://bad"}).status_code == 422
    # other tenants can't attach to my job
    assert client.post(f"{API}/documents/link", headers=other, json={"owner_type": "job", "owner_id": job["id"],
                                                                    "title": "spam", "url": "https://x.in"}).status_code == 404
    # freelancers can read attachments of an open job
    docs = client.get(f"{API}/documents?owner_type=job&owner_id={job['id']}", headers=fh).json()
    assert {d["kind"] for d in docs} == {"file", "url"}
    dl = client.get(docs[-1]["download_url"] if docs[-1]["kind"] == "file" else docs[0]["download_url"], headers=fh)
    assert dl.status_code == 200 and dl.content == pdf and dl.headers["content-type"] == "application/pdf"
    assert client.get(f"{API}/documents?owner_type=job&owner_id={job['id']}").status_code == 401
    assert client.delete(f"{API}/documents/{up.json()['id']}", headers=fh).status_code == 404
    assert client.delete(f"{API}/documents/{up.json()['id']}", headers=ch).status_code == 200
    # closed job: attachments hidden from outsiders
    client.put(f"{API}/jobs/{job['id']}", headers=ch, json={"status": "closed"})
    assert client.get(f"{API}/documents?owner_type=job&owner_id={job['id']}", headers=fh).status_code == 404


def test_upload_rules(client):
    ch, _ = signup(client, "client", "c@x.in")
    job = post_job(client, ch, ["A"]).json()
    r = client.post(f"{API}/documents/upload", headers=ch, data={"owner_type": "job", "owner_id": job["id"]},
                    files={"file": ("evil.exe", b"MZ...", "application/octet-stream")})
    assert r.status_code == 400
    r = client.post(f"{API}/documents/upload", headers=ch, data={"owner_type": "job", "owner_id": job["id"]},
                    files={"file": ("fake.pdf", b"hello", "application/pdf")})
    assert r.status_code == 400
    r = client.post(f"{API}/documents/upload", headers=ch, data={"owner_type": "nope", "owner_id": 1},
                    files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_order_documents_are_private_to_parties(client):
    fh, _ = signup(client, "freelancer", "f@x.in")
    s = client.post(f"{API}/services", headers=fh, json={"title": "Write a pitch deck", "price": 3000}).json()
    ch, _ = signup(client, "client", "c@x.in")
    o = client.post(f"{API}/services/{s['id']}/order", headers=ch, json={}).json()
    other, _ = signup(client, "freelancer", "x@x.in")
    r = client.post(f"{API}/documents/upload", headers=fh, data={"owner_type": "order", "owner_id": o["id"], "title": "Draft"},
                    files={"file": ("draft.txt", b"v1", "text/plain")})
    assert r.status_code == 200
    assert len(client.get(f"{API}/documents?owner_type=order&owner_id={o['id']}", headers=ch).json()) == 1
    assert client.get(f"{API}/documents?owner_type=order&owner_id={o['id']}", headers=other).status_code == 404
    assert client.get(r.json()["download_url"], headers=other).status_code == 404


def test_control_room_overview_and_lists(client):
    ch, _ = signup(client, "client", "c@x.in", company="Acme")
    freelancer_with_skills(client, "f@x.in", ["Python"], 3)
    post_job(client, ch, ["Python"])
    pay_demo(client, ch, purpose="subscription", plan_type="PREMIUM", months=1)
    ah = admin_headers(client)
    ov = client.get(f"{API}/admin/overview", headers=ah).json()
    assert ov["users"]["clients"] == 1 and ov["users"]["freelancers"] == 1
    assert ov["money"]["subscription_revenue"] == 999.0 and ov["money"]["mrr"] == 999
    assert ov["plans"]["PREMIUM"] == 1 and len(ov["series"]) == 30 and ov["series"][-1]["revenue"] == 999.0
    assert ov["marketplace"]["matches"] == 1
    assert len(client.get(f"{API}/admin/users?role=client", headers=ah).json()) == 1
    assert client.get(f"{API}/admin/payments?status=paid", headers=ah).json()[0]["client"]["company_name"] == "Acme"
    assert len(client.get(f"{API}/admin/jobs", headers=ah).json()) == 1
    assert client.post(f"{API}/admin/rematch-all", headers=ah).json()["jobs_rematched"] == 1
    me = client.get(f"{API}/auth/me", headers=ah).json()
    assert client.patch(f"{API}/admin/users/{me['id']}", headers=ah, json={"is_active": False}).status_code == 400
    assert "app.plugins.ranking.standard_weighted" in client.get(f"{API}/admin/tools/plugins", headers=ah).json()["ranking_plugins"]


def test_websocket_requires_token_and_delivers_matches(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws?token=bad") as ws:
            ws.receive_json()
    ch, _ = signup(client, "client", "c@x.in")
    post_job(client, ch, ["Python"])
    token = ch["Authorization"].split()[1]
    with client.websocket_connect(f"/ws?token={token}") as ws:
        freelancer_with_skills(client, "live@x.in", ["Python"], 2)
        msg = ws.receive_json()
        assert msg["type"] == "new_match" and "user_ids" not in msg
