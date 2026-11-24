import os
import sys
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
# Set TEST_DATABASE_URL (e.g. a throwaway Postgres) to run the suite against Postgres; default is SQLite.
os.environ["SQLALCHEMY_DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ.pop("DATABASE_URL", None)
os.environ["ADMIN_EMAIL"] = "admin@test.dev"
os.environ["ADMIN_PASSWORD"] = "Admin@12345"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from app.main import app  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.core import ratelimit  # noqa: E402
from app.services.pdfgen import make_pdf  # noqa: E402,F401

API = "/api/v1"
PASSWORD = "Passw0rd!"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    ratelimit.reset()
    with TestClient(app) as c:
        yield c


def signup(c, role, email, name=None, company=None, headline=None):
    """Register and return (headers, user). Uses a separate cookie jar per user."""
    r = c.post(f"{API}/auth/register", json={"role": role, "name": name or email.split("@")[0], "email": email,
                                             "password": PASSWORD, "company_name": company, "headline": headline})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


def login(c, email, password):
    r = c.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def admin_headers(c):
    return login(c, "admin@test.dev", "Admin@12345")


def freelancer_with_skills(c, email, skills, exp, **extra):
    h, u = signup(c, "freelancer", email)
    r = c.put(f"{API}/freelancers/me", headers=h, json={"skills": skills, "experience_years": exp, **extra})
    assert r.status_code == 200, r.text
    return h, r.json()


def post_job(c, h, skills, exp=0, title="ERP Consultant", **extra):
    return c.post(f"{API}/jobs", headers=h, json={"title": title, "description": "Overview",
                                                  "required_skills": skills, "min_experience_years": exp, **extra})


def pay_demo(c, h, **checkout):
    r = c.post(f"{API}/payments/checkout", headers=h, json=checkout)
    assert r.status_code == 200, r.text
    pid = r.json()["payment_id"]
    r = c.post(f"{API}/payments/{pid}/demo-complete", headers=h, json={"outcome": "success"})
    assert r.status_code == 200, r.text
    return r.json()
