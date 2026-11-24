from tests.conftest import API, signup, admin_headers, make_pdf, freelancer_with_skills, post_job


def test_matching_ranking_threshold_and_aliases(client):
    ch, _ = signup(client, "client", "c@x.in", company="Acme")
    freelancer_with_skills(client, "full@x.in", ["Python 3.11", "Postgres", "AWS"], 6)
    freelancer_with_skills(client, "half@x.in", ["python", "sql"], 2)
    freelancer_with_skills(client, "none@x.in", ["Cooking"], 0)
    job = post_job(client, ch, ["Python", "PostgreSQL", "AWS"], 4).json()
    m = client.get(f"{API}/jobs/{job['id']}/matches", headers=ch).json()
    assert [x["name"] for x in m["matches"]] == ["full"]  # half: 1/3 skills → 53? no: (33*.7+50*.3)=38 < 50
    assert m["matches"][0]["score"] == 100.0


def test_freelancer_joining_later_gets_matched_and_sees_recommendation(client):
    ch, _ = signup(client, "client", "c@x.in")
    job = post_job(client, ch, ["SAP", "ERP"], 3).json()
    fh, _ = freelancer_with_skills(client, "late@x.in", ["SAP ERP", "ERP"], 5)
    assert client.get(f"{API}/jobs/{job['id']}/matches", headers=ch).json()["total_matches"] == 1
    rec = client.get(f"{API}/freelancers/me/recommended-jobs", headers=fh).json()
    assert rec[0]["job"]["id"] == job["id"] and rec[0]["score"] == 100.0


def test_hidden_profile_not_matched_or_listed(client):
    ch, _ = signup(client, "client", "c@x.in")
    fh, prof = freelancer_with_skills(client, "f@x.in", ["Go"], 5, is_public=False)
    job = post_job(client, ch, ["Go"]).json()
    assert client.get(f"{API}/jobs/{job['id']}/matches", headers=ch).json()["total_matches"] == 0
    assert client.get(f"{API}/freelancers").json()["total"] == 0
    assert client.get(f"{API}/freelancers/{prof['id']}").status_code == 404
    assert client.get(f"{API}/freelancers/{prof['id']}", headers=fh).status_code == 200  # owner can see


def test_free_plan_limits_and_contact_masking(client):
    ch, _ = signup(client, "client", "c@x.in")
    for i in range(5):
        freelancer_with_skills(client, f"f{i}@x.in", ["Python"], i + 1)
    j1 = post_job(client, ch, ["Python"], 5, title="Job one").json()
    assert post_job(client, ch, ["A"], title="Job two").status_code == 200
    r = post_job(client, ch, ["A"], title="Job three")
    assert r.status_code == 403 and "FREE" in r.json()["detail"]
    m = client.get(f"{API}/jobs/{j1['id']}/matches", headers=ch).json()
    assert m["visible_matches"] == 3 and m["hidden_matches"] == 2 and "***" in m["matches"][0]["email"]
    assert [x["experience_years"] for x in m["matches"]] == [5, 4, 3]
    # closing frees a slot; reopening over the limit is blocked
    client.put(f"{API}/jobs/{j1['id']}", headers=ch, json={"status": "closed"})
    assert post_job(client, ch, ["A"], title="Job three").status_code == 200
    assert client.put(f"{API}/jobs/{j1['id']}", headers=ch, json={"status": "open"}).status_code == 403


def test_public_browse_shows_only_open_jobs_and_active_services(client):
    ch, _ = signup(client, "client", "c@x.in", company="Acme")
    open_job = post_job(client, ch, ["Python"], title="Open role", category="Engineering").json()
    closed = post_job(client, ch, ["Python"], title="Closed role").json()
    client.put(f"{API}/jobs/{closed['id']}", headers=ch, json={"status": "closed"})
    jobs = client.get(f"{API}/jobs").json()
    assert [j["title"] for j in jobs["items"]] == ["Open role"]
    assert jobs["items"][0]["client"]["company_name"] == "Acme" and "email" not in jobs["items"][0]["client"]
    assert client.get(f"{API}/jobs/{closed['id']}").status_code == 404
    assert client.get(f"{API}/jobs?skill=pyth").json()["total"] == 1
    assert client.get(f"{API}/jobs?q=nothing-like-this").json()["total"] == 0

    fh, _ = signup(client, "freelancer", "f@x.in")
    s1 = client.post(f"{API}/services", headers=fh, json={"title": "Build a FastAPI backend", "price": 25000,
                                                           "category": "Engineering", "skills": "Python, FastAPI"}).json()
    s2 = client.post(f"{API}/services", headers=fh, json={"title": "Paused offer here", "price": 900,
                                                           "status": "paused"}).json()
    svc = client.get(f"{API}/services").json()
    assert [s["id"] for s in svc["items"]] == [s1["id"]]
    assert client.get(f"{API}/services/{s2['id']}").status_code == 404
    assert client.get(f"{API}/services/{s2['id']}", headers=fh).status_code == 200
    assert "Engineering" in client.get(f"{API}/services/categories").json()
    prof = client.get(f"{API}/freelancers/{s1['consultant_id']}").json()
    assert "email" not in prof and len(prof["services"]) == 1


def test_profile_links_validation(client):
    fh, _ = signup(client, "freelancer", "f@x.in")
    ok = client.put(f"{API}/freelancers/me", headers=fh, json={"links": [{"label": "GitHub", "url": "https://github.com/me"}]})
    assert ok.status_code == 200 and ok.json()["links"][0]["url"] == "https://github.com/me"
    bad = client.put(f"{API}/freelancers/me", headers=fh, json={"links": [{"label": "x", "url": "javascript:alert(1)"}]})
    assert bad.status_code == 422


def test_cv_upload_fills_profile(client):
    ch, _ = signup(client, "client", "c@x.in")
    post_job(client, ch, ["Python", "SQL", "Docker"], 5)
    fh, _ = signup(client, "freelancer", "ravi@mail.com", name="Ravi Kumar")
    pdf = make_pdf(["Ravi Kumar", "ravi@mail.com +91 98765 43210", "Backend developer with 7 years of experience.",
                    "Skills: Python, SQL, Docker, FastAPI", "Education", "B.Tech"])
    r = client.post(f"{API}/freelancers/me/cv", headers=fh, files={"file": ("cv.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"Python", "SQL", "Docker", "FastAPI"} <= set(body["profile"]["skills"])
    assert body["experience_years"] == 7.0 and body["new_matches"] == 1
    docs = client.get(f"{API}/documents?owner_type=consultant&owner_id={body['profile']['id']}", headers=ch).json()
    assert docs[0]["title"] == "CV" and docs[0]["download_url"]
    assert client.post(f"{API}/freelancers/me/cv", headers=fh,
                       files={"file": ("cv.pdf", b"not a pdf", "application/pdf")}).status_code == 400


def test_proposals_flow(client):
    ch, _ = signup(client, "client", "c@x.in")
    other_h, _ = signup(client, "client", "other@x.in")
    fh, prof = freelancer_with_skills(client, "f@x.in", ["React"], 3)
    job = post_job(client, ch, ["React"], 2).json()
    body = {"cover_letter": "I have built many React dashboards for SaaS.", "bid_amount": 40000, "estimated_days": 14}
    p = client.post(f"{API}/jobs/{job['id']}/proposals", headers=fh, json=body)
    assert p.status_code == 200
    assert client.post(f"{API}/jobs/{job['id']}/proposals", headers=fh, json=body).status_code == 400  # duplicate
    assert client.post(f"{API}/jobs/{job['id']}/proposals", headers=fh, json={**body, "cover_letter": "short"}).status_code == 422
    props = client.get(f"{API}/jobs/{job['id']}/proposals", headers=ch).json()
    assert props[0]["freelancer"]["id"] == prof["id"] and props[0]["match_score"] == 100.0
    assert client.get(f"{API}/jobs/{job['id']}/proposals", headers=other_h).status_code == 404
    pid = p.json()["id"]
    assert client.post(f"{API}/proposals/{pid}/accept", headers=other_h).status_code == 404
    assert client.post(f"{API}/proposals/{pid}/shortlist", headers=ch).json()["status"] == "shortlisted"
    order = client.post(f"{API}/proposals/{pid}/accept", headers=ch).json()
    assert order["status"] == "pending_payment" and order["amount"] == 40000.0 and order["platform_fee"] == 4000.0
    mine = client.get(f"{API}/proposals/mine", headers=fh).json()
    assert mine[0]["status"] == "accepted" and mine[0]["order_id"] == order["id"]
    # cancelling the unpaid order puts the proposal back on the shortlist
    client.post(f"{API}/orders/{order['id']}/cancel", headers=ch)
    assert client.get(f"{API}/proposals/mine", headers=fh).json()[0]["status"] == "shortlisted"


def test_cannot_apply_to_closed_job_and_withdraw(client):
    ch, _ = signup(client, "client", "c@x.in")
    fh, _ = signup(client, "freelancer", "f@x.in")
    job = post_job(client, ch, ["A"]).json()
    body = {"cover_letter": "Twenty characters at least here.", "bid_amount": 1000}
    pid = client.post(f"{API}/jobs/{job['id']}/proposals", headers=fh, json=body).json()["id"]
    assert client.post(f"{API}/proposals/{pid}/withdraw", headers=fh).json()["status"] == "withdrawn"
    assert client.post(f"{API}/proposals/{pid}/accept", headers=ch).status_code == 400
    client.put(f"{API}/jobs/{job['id']}", headers=ch, json={"status": "closed"})
    fh2, _ = signup(client, "freelancer", "f2@x.in")
    assert client.post(f"{API}/jobs/{job['id']}/proposals", headers=fh2, json=body).status_code in (400, 404)


def test_job_description_fields_and_validation(client):
    ch, _ = signup(client, "client", "c@x.in")
    r = post_job(client, ch, ["Python"], 3, responsibilities="Build APIs\nReview code", requirements="Fintech a plus",
                 budget_type="hourly", budget_min=1500, budget_max=2500, location_type="hybrid",
                 location="Bengaluru", deadline="2027-01-15", category="Engineering")
    assert r.status_code == 200
    j = client.get(f"{API}/jobs/{r.json()['id']}").json()
    assert j["budget_type"] == "hourly" and j["location"] == "Bengaluru" and j["deadline"] == "2027-01-15"
    assert post_job(client, ch, ["A"], budget_min=5000, budget_max=100).status_code == 422
    assert client.put(f"{API}/jobs/{j['id']}", headers=ch, json={"budget_max": 10}).status_code == 400


def test_admin_can_manage_and_delete(client):
    ah = admin_headers(client)
    ch, cu = signup(client, "client", "c@x.in")
    r = client.post(f"{API}/freelancers", headers=ah, json={"name": "Walk-in", "email": "walk@x.in", "skills": ["SAP"],
                                                             "experience_years": 9})
    assert r.status_code == 200
    j = client.post(f"{API}/jobs?client_id={cu['client_id']}", headers=ah,
                    json={"title": "Admin posted", "required_skills": ["SAP"]}).json()
    assert client.get(f"{API}/jobs/{j['id']}/matches", headers=ah).json()["total_matches"] == 1
    # the walk-in can later sign up and claim the profile an admin made for their email
    fh, fu = signup(client, "freelancer", "walk@x.in")
    assert fu["consultant_id"] == r.json()["id"]
    assert client.delete(f"{API}/clients/{cu['client_id']}", headers=ah).status_code == 200
    assert client.get(f"{API}/jobs/{j['id']}", headers=ah).status_code == 404
