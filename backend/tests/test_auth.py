from tests.conftest import API, PASSWORD, signup, login, admin_headers


def test_register_login_me(client):
    h, u = signup(client, "client", "asha@acme.in", company="Acme")
    assert u["role"] == "client" and u["plan"] == "FREE" and u["client_id"]
    me = client.get(f"{API}/auth/me", headers=h).json()
    assert me["email"] == "asha@acme.in" and me["company_name"] == "Acme"
    assert client.post(f"{API}/auth/login", json={"email": "asha@acme.in", "password": "wrong-pass1"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": "nobody@x.in", "password": "wrong-pass1"}).json()["detail"] \
        == "Wrong email or password"  # same message: no account enumeration
    login(client, "ASHA@acme.in", PASSWORD)


def test_register_validation(client):
    r = client.post(f"{API}/auth/register", json={"role": "client", "name": "a", "email": "a@a.in", "password": "12345678"})
    assert r.status_code == 400  # digits only
    r = client.post(f"{API}/auth/register", json={"role": "admin", "name": "a", "email": "a@a.in", "password": PASSWORD})
    assert r.status_code == 422  # can't self-register as admin
    signup(client, "freelancer", "dup@x.in")
    r = client.post(f"{API}/auth/register", json={"role": "client", "name": "a", "email": "DUP@x.in", "password": PASSWORD})
    assert r.status_code == 400


def test_same_company_name_creates_separate_companies(client):
    h1, u1 = signup(client, "client", "a@one.in", company="Globex")
    h2, u2 = signup(client, "client", "b@two.in", company="Globex")
    assert u1["client_id"] != u2["client_id"]
    j = client.post(f"{API}/jobs", headers=h1, json={"title": "Secret job", "required_skills": ["X"]}).json()
    assert client.get(f"{API}/jobs/mine", headers=h2).json() == []
    assert client.get(f"{API}/jobs/{j['id']}/matches", headers=h2).status_code == 404


def test_refresh_rotation_and_reuse_detection(client):
    signup(client, "client", "r@x.in")
    old = client.cookies.get("tm_refresh")
    r = client.post(f"{API}/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    new = client.cookies.get("tm_refresh")
    assert new and new != old
    # replay the old (rotated) token → every session ends
    client.cookies.set("tm_refresh", old, path="/api/v1/auth")
    assert client.post(f"{API}/auth/refresh").status_code == 401
    client.cookies.set("tm_refresh", new, path="/api/v1/auth")
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_logout_and_logout_all(client):
    h, _ = signup(client, "freelancer", "f@x.in")
    assert client.post(f"{API}/auth/logout").status_code == 200
    assert client.post(f"{API}/auth/refresh").status_code == 401
    login(client, "f@x.in", PASSWORD)
    h = login(client, "f@x.in", PASSWORD)
    r = client.post(f"{API}/auth/logout-all", headers=h)
    assert r.json()["sessions_ended"] == 2
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_change_password(client):
    h, _ = signup(client, "client", "c@x.in")
    assert client.post(f"{API}/auth/change-password", headers=h,
                       json={"current_password": "nope-nope1", "new_password": "NewPass#2026"}).status_code == 400
    r = client.post(f"{API}/auth/change-password", headers=h,
                    json={"current_password": PASSWORD, "new_password": "NewPass#2026"})
    assert r.status_code == 200
    login(client, "c@x.in", "NewPass#2026")


def test_disabled_user_is_locked_out(client):
    h, u = signup(client, "freelancer", "bad@x.in")
    ah = admin_headers(client)
    assert client.patch(f"{API}/admin/users/{u['id']}", headers=ah, json={"is_active": False}).status_code == 200
    assert client.get(f"{API}/auth/me", headers=h).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": "bad@x.in", "password": PASSWORD}).status_code == 403


def test_login_rate_limit(client):
    for _ in range(10):
        client.post(f"{API}/auth/login", json={"email": "x@x.in", "password": "whatever1"})
    assert client.post(f"{API}/auth/login", json={"email": "x@x.in", "password": "whatever1"}).status_code == 429


def test_role_guards(client):
    fh, _ = signup(client, "freelancer", "f@x.in")
    ch, _ = signup(client, "client", "c@x.in")
    assert client.get(f"{API}/admin/overview").status_code == 401
    assert client.get(f"{API}/admin/overview", headers=ch).status_code == 403
    assert client.post(f"{API}/jobs", headers=fh, json={"title": "Nope job"}).status_code == 403
    assert client.post(f"{API}/services", headers=ch, json={"title": "Nope svc", "price": 500}).status_code == 403
    assert client.get(f"{API}/admin/overview", headers=admin_headers(client)).status_code == 200


def test_unknown_api_route_is_json_404(client):
    r = client.get(f"{API}/does-not-exist")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert client.get("/health").json()["status"] == "ok"
