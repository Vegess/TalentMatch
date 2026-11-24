"""Fill the database with a realistic demo marketplace.

    python seed_demo.py            # from the backend folder

Creates an admin, 3 client companies (one per plan), 10 freelancers with profiles and services,
6 job descriptions with attachments, proposals, orders in different stages and payments.
Safe to run more than once (skips if the demo admin already exists).

Demo logins (password for everyone: Demo@1234, admin: Admin@12345):
  admin@talentmatch.dev       · control room
  priya@technova.in           · client (PREMIUM)
  arjun@buildright.in         · client (FREE)
  rahul.verma@mail.com        · freelancer
"""
import datetime as dt
import os
import sys

from app.core.database import run_migrations, SessionLocal
from app.core.plugin_loader import PluginLoader
from app.core.security import hash_password
from app.core import config
from app.models import User, Client, Consultant, Job, Service, Proposal, Order, Payment, Document, DocumentBlob
from app.models._time import utcnow
from app.services import matching, payments as pay, payouts
from app.services.subscriptions import start_subscription
from app.api.v1.endpoints.auth import create_user

DEMO_PASSWORD = "Demo@1234"
ADMIN_EMAIL, ADMIN_PASSWORD = "admin@talentmatch.dev", "Admin@12345"

CLIENTS = [
    ("Priya Sharma", "priya@technova.in", "TechNova Solutions", "PREMIUM", "SaaS", "https://technova.example.com"),
    ("Arjun Mehta", "arjun@buildright.in", "BuildRight Manufacturing", "FREE", "Manufacturing", None),
    ("Neha Rao", "neha@finedge.com", "FinEdge Capital", "ENTERPRISE", "Financial services", "https://finedge.example.com"),
    ("Emily Clarke", "emily@northwind.io", "Northwind Labs", "PREMIUM", "Software", "https://northwind.example.com"),
]
CLIENT_GEO = {"emily@northwind.io": ("US", "America/New_York")}
FREELANCERS = [
    ("Rahul Verma", "rahul.verma@mail.com", "Senior Python backend engineer", "Pune", 2500,
     ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"], 7, "github.com/rahulverma"),
    ("Sneha Iyer", "sneha.iyer@mail.com", "React & TypeScript frontend developer", "Bengaluru", 2000,
     ["React", "TypeScript", "Node", "UI/UX", "Tailwind"], 5, "dribbble.com/snehaiyer"),
    ("Vikram Singh", "vikram.singh@mail.com", "SAP S/4HANA implementation lead", "Gurugram", 4500,
     ["SAP", "ERP", "Project Management", "Supply Chain"], 12, "linkedin.com/in/vikramsingh"),
    ("Ananya Gupta", "ananya.g@mail.com", "Data scientist — risk and forecasting", "Hyderabad", 2200,
     ["Python", "Machine Learning", "Pandas", "SQL"], 4, "kaggle.com/ananyag"),
    ("Karthik Nair", "karthik.nair@mail.com", "Java / Spring microservices architect", "Kochi", 3000,
     ["Java", "Spring", "Kubernetes", "AWS"], 9, "github.com/karthiknair"),
    ("Meera Joshi", "meera.joshi@mail.com", "Lean Six Sigma Black Belt", "Ahmedabad", 3500,
     ["Lean", "Six Sigma", "Quality", "ISO", "Manufacturing"], 10, "linkedin.com/in/meerajoshi"),
    ("Aditya Kulkarni", "aditya.k@mail.com", "Full-stack Django + React developer", "Nagpur", 1500,
     ["Python", "Django", "React", "SQL"], 3, "github.com/adityak"),
    ("Fatima Khan", "fatima.khan@mail.com", "Finance & Power BI reporting consultant", "Mumbai", 2800,
     ["Finance", "Excel", "PowerBI", "Accounting"], 6, "linkedin.com/in/fatimakhan"),
    ("Rohan Das", "rohan.das@mail.com", "DevOps & cloud infrastructure engineer", "Kolkata", 2600,
     ["DevOps", "Docker", "Kubernetes", "Terraform", "CI/CD", "AWS"], 5, "github.com/rohandas"),
    ("Divya Menon", "divya.menon@mail.com", "Agile delivery manager / Scrum Master", "Chennai", 2400,
     ["Agile", "Scrum", "Project Management", "Jira"], 8, "linkedin.com/in/divyamenon"),
    ("Lucía Fernández", "lucia.fernandez@mail.com", "Product designer — SaaS dashboards", "Madrid", 45,
     ["Figma", "UI/UX", "Design Systems", "React"], 7, "dribbble.com/luciaf"),
    ("James Carter", "james.carter@mail.com", "Data engineer — Airflow, dbt, Snowflake", "Austin", 70,
     ["Python", "SQL", "Airflow", "dbt", "AWS"], 9, "github.com/jcarter"),
]
FREELANCER_GEO = {"lucia.fernandez@mail.com": ("ES", "Europe/Madrid", ["Spanish", "English"], 9, 18),
                  "james.carter@mail.com": ("US", "America/Chicago", ["English"], 8, 17)}
VERIFIED = {"rahul.verma@mail.com", "vikram.singh@mail.com", "lucia.fernandez@mail.com"}
SERVICES = {
    "rahul.verma@mail.com": [("Production-ready FastAPI backend with auth and Postgres", "Engineering", 45000, 14,
                              "REST API with JWT auth\nPostgreSQL schema + migrations\nDocker setup\nOpenAPI docs",
                              ["Python", "FastAPI", "PostgreSQL"]),
                             ("Code review and performance audit of a Python service", "Engineering", 12000, 4,
                              "Written report\n1-hour walkthrough call", ["Python"])],
    "sneha.iyer@mail.com": [("Responsive React dashboard from your Figma designs", "Design & Frontend", 35000, 12,
                             "React + TypeScript components\nTailwind styling\nDeployed preview", ["React", "TypeScript"])],
    "vikram.singh@mail.com": [("SAP S/4HANA readiness assessment", "ERP & Operations", 90000, 21,
                               "Process gap analysis\nMigration roadmap\nRisk register", ["SAP", "ERP"])],
    "ananya.g@mail.com": [("Sales forecasting model with a monthly accuracy report", "Data & AI", 30000, 10,
                           "Notebook + trained model\nAccuracy report", ["Python", "Machine Learning"])],
    "meera.joshi@mail.com": [("Value-stream mapping workshop for one production line", "ERP & Operations", 40000, 7,
                              "On-site workshop (2 days)\nCurrent and future state maps", ["Lean", "Manufacturing"])],
    "fatima.khan@mail.com": [("Power BI finance dashboard (P&L, cash flow)", "Finance", 22000, 8,
                              "Power BI file\nData model documentation", ["PowerBI", "Finance"])],
    "lucia.fernandez@mail.com": [("Design system and component library in Figma", "Design & Frontend", 1800, 14,
                                  "Figma library\nTokens\nUsage guidelines", ["Figma", "Design Systems"])],
    "rohan.das@mail.com": [("CI/CD pipeline and Kubernetes deploy for one service", "Engineering", 28000, 7,
                            "GitHub Actions pipeline\nHelm chart\nRunbook", ["DevOps", "Kubernetes"])],
}
JOBS = [
    ("priya@technova.in", "Senior Python Backend Consultant", "Engineering",
     "We're scaling our B2B SaaS and need an experienced backend engineer to own our public API.",
     "Design and build REST endpoints in FastAPI\nModel data in PostgreSQL and write migrations\n"
     "Containerise services with Docker\nReview pull requests from two junior engineers",
     "Experience with multi-tenant SaaS is a plus\nComfortable with async Python",
     ["Python", "FastAPI", "PostgreSQL", "Docker"], 5, "fixed", 150000, 250000, "remote", None, 45),
    ("priya@technova.in", "Frontend React Developer", "Design & Frontend",
     "Revamp the customer dashboard with a modern, accessible React UI.",
     "Turn Figma designs into React components\nImprove page load times\nWrite component tests",
     "Tailwind CSS experience preferred", ["React", "TypeScript", "UI/UX"], 3, "hourly", 1500, 2200, "hybrid",
     "Bengaluru", 30),
    ("arjun@buildright.in", "SAP ERP Implementation Lead", "ERP & Operations",
     "Roll out SAP S/4HANA across two plants in Gujarat.",
     "Run fit-gap workshops\nLead a team of 4 functional consultants\nOwn the cut-over plan",
     "Manufacturing domain experience required", ["SAP", "ERP", "Project Management"], 8, "fixed", 800000,
     1200000, "onsite", "Vadodara", 90),
    ("arjun@buildright.in", "Lean Manufacturing Consultant", "ERP & Operations",
     "Reduce waste on our assembly line and train supervisors in lean methods.",
     "Map the current value stream\nRun kaizen events\nTrain 12 supervisors", None,
     ["Lean", "Six Sigma", "Manufacturing"], 6, "fixed", 200000, 350000, "onsite", "Vadodara", 60),
    ("neha@finedge.com", "Data Scientist (Credit Risk Models)", "Data & AI",
     "Build and validate credit-risk scoring models for our lending book.",
     "Feature engineering on bureau data\nTrain and validate scorecards\nDocument models for audit",
     "RBI model-risk guidelines familiarity is a plus", ["Python", "Machine Learning", "SQL"], 3, "hourly", 2000,
     3000, "remote", None, 40),
    ("neha@finedge.com", "Cloud DevOps Engineer", "Engineering",
     "Migrate our workloads from VMs to Kubernetes on AWS.",
     "Write Terraform for EKS\nSet up CI/CD with GitHub Actions\nObservability with Prometheus/Grafana", None,
     ["Kubernetes", "Docker", "AWS", "Terraform"], 4, "fixed", 300000, 450000, "remote", None, 50),
    ("emily@northwind.io", "Senior Data Engineer (Airflow + dbt)", "Data & AI",
     "Own our analytics pipelines as we scale to millions of events a day.",
     "Build Airflow DAGs and dbt models\nOptimise Snowflake costs\nMentor one analyst",
     "US time-zone overlap of 4 hours", ["Python", "SQL", "Airflow", "dbt"], 5, "hourly", 60, 90, "remote", None, 30),
]


def _pdf(lines):
    from app.services.pdfgen import make_pdf
    return make_pdf(lines)


def main():
    run_migrations()
    PluginLoader().load_plugins()
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == ADMIN_EMAIL).first():
            print("Demo data already present — nothing to do.")
            return
        db.add(User(email=ADMIN_EMAIL, name="Platform Admin", role="admin", password_hash=hash_password(ADMIN_PASSWORD)))
        db.commit()
        clients = {}
        for name, email, company, plan, industry, website in CLIENTS:
            u = create_user(db, role="client", name=name, email=email, password=DEMO_PASSWORD, company_name=company)
            c = db.query(Client).filter(Client.owner_user_id == u.id).first()
            c.industry, c.website = industry, website
            cc, tz = CLIENT_GEO.get(email, ("IN", "Asia/Kolkata"))
            c.country, c.timezone = cc, tz
            from app.core.geo import default_currency
            c.currency = default_currency(cc)
            c.about = f"{company} is a {industry.lower()} company" + (" based in India." if cc == "IN" else f" ({cc}).")
            db.commit()
            if plan != "FREE":
                months = 12 if plan == "ENTERPRISE" else 1
                from app.core.plans import PLANS
                from app.core.plans import price as plan_price
                p = Payment(user_id=u.id, client_id=c.id, purpose="subscription", plan_type=plan, months=months,
                            amount_paise=plan_price(plan, c.currency) * months * 100, currency=c.currency, provider="demo",
                            provider_order_id=f"demo_order_seed_{c.id}")
                db.add(p)
                db.flush()
                pay.fulfil(db, p, f"demo_pay_seed_{c.id}")
            clients[email] = c
        freelancers = {}
        for name, email, headline, city, rate, skills, exp, link in FREELANCERS:
            u = create_user(db, role="freelancer", name=name, email=email, password=DEMO_PASSWORD, headline=headline)
            f = db.query(Consultant).filter(Consultant.user_id == u.id).first()
            f.location, f.hourly_rate, f.skills, f.experience_years = city, rate, skills, exp
            where = "across India" if email not in FREELANCER_GEO else "in Europe and North America"
            f.bio = (f"{headline} with {exp} years of experience. I work with startups and enterprises {where} "
                     f"and focus on clear communication and on-time delivery.")
            f.links = [{"label": link.split(".")[0].capitalize(), "url": f"https://{link}"}]
            f.phone = "+91 98" + str(10000000 + abs(hash(email)) % 89999999)[:8]
            cc, tz, langs, ws, we = FREELANCER_GEO.get(email, ("IN", "Asia/Kolkata", ["English", "Hindi"], 10, 19))
            from app.core.geo import default_currency
            f.country, f.timezone, f.languages, f.work_start_hour, f.work_end_hour = cc, tz, langs, ws, we
            f.currency = default_currency(cc)
            if cc != "IN":
                f.phone = None
            if email in VERIFIED:
                f.verified_at = utcnow()
            freelancers[email] = f
        db.commit()
        # Demo payout accounts (only in demo mode — never call the real Razorpay API from the seed).
        if payouts.mode() == "demo":
            for email, upi in [("rahul.verma@mail.com", "rahul.verma@okicici"), ("sneha.iyer@mail.com", "sneha.iyer@oksbi"),
                               ("fatima.khan@mail.com", "fatima.khan@okhdfcbank")]:
                f = freelancers[email]
                payouts.setup_account(db, f, method="upi", beneficiary_name=f.name, account_number=None, ifsc=None,
                                      vpa=upi, phone=None)
        services = {}
        for email, rows in SERVICES.items():
            for title, cat, price, days, deliv, sk in rows:
                s = Service(consultant_id=freelancers[email].id, title=title, category=cat, price=price,
                            currency=freelancers[email].currency,
                            delivery_days=days, deliverables=deliv, skills=sk,
                            description=f"{title}. Fixed scope, fixed price, delivered in {days} days.")
                db.add(s)
                services[title] = s
        db.commit()
        jobs = []
        for (email, title, cat, desc, resp, req, skills, exp, btype, bmin, bmax, ltype, loc, days) in JOBS:
            j = Job(client_id=clients[email].id, title=title, category=cat, description=desc, responsibilities=resp,
                    requirements=req, required_skills=skills, min_experience_years=exp, budget_type=btype,
                    budget_min=bmin, budget_max=bmax, location_type=ltype, location=loc,
                    currency=clients[email].currency,
                    deadline=(utcnow() + dt.timedelta(days=days)).date(), status="open")
            db.add(j)
            jobs.append(j)
        db.commit()
        # attachments: a generated JD PDF + a link
        jd = _pdf(["Senior Python Backend Consultant - TechNova Solutions", "Scope: public API, multi-tenant data model,",
                   "Docker deployment. Duration: 3 months. Remote."])
        d = Document(owner_type="job", owner_id=jobs[0].id, kind="file", title="Full job description (PDF)",
                     filename="technova-backend-jd.pdf", content_type="application/pdf", size_bytes=len(jd))
        d.blob = DocumentBlob(data=jd)
        db.add(d)
        db.add(Document(owner_type="job", owner_id=jobs[1].id, kind="url", title="Figma designs",
                        url="https://www.figma.com/"))
        db.add(Document(owner_type="consultant", owner_id=freelancers["rahul.verma@mail.com"].id, kind="url",
                        title="Portfolio: case studies", url="https://github.com/"))
        db.commit()
        matching.rematch_all(db)

        # proposals
        def propose(email, job, bid, days, letter):
            p = Proposal(job_id=job.id, consultant_id=freelancers[email].id, bid_amount=bid, estimated_days=days,
                         cover_letter=letter)
            db.add(p)
            db.flush()
            return p
        propose("rahul.verma@mail.com", jobs[0], 210000, 60, "I've built three multi-tenant FastAPI platforms and "
                "can start next week. Happy to share code samples.")
        propose("aditya.k@mail.com", jobs[0], 160000, 75, "Strong Python and SQL background; keen to grow into "
                "this role and can commit full-time.")
        p_hire = propose("sneha.iyer@mail.com", jobs[1], 120000, 40, "I recently shipped a similar analytics "
                         "dashboard in React + TypeScript. Portfolio linked on my profile.")
        propose("vikram.singh@mail.com", jobs[2], 1100000, 120, "12 years of SAP rollouts in manufacturing, "
                "including two multi-plant S/4HANA migrations.")
        p_hire.status = "accepted"
        db.commit()

        def order(client_email, f_email, title, amount_rs, status, **kw):
            amount = amount_rs * 100
            o = Order(client_id=clients[client_email].id, consultant_id=freelancers[f_email].id, title=title,
                      currency=clients[client_email].currency,
                      amount_paise=amount, platform_fee_paise=round(amount * config.PLATFORM_FEE_PERCENT / 100),
                      status="pending_payment", **kw)
            db.add(o)
            db.flush()
            if status != "pending_payment":
                c = clients[client_email]
                p = Payment(user_id=c.owner_user_id, client_id=c.id, purpose="order", order_id=o.id,
                            amount_paise=amount, currency=o.currency, provider="demo", provider_order_id=f"demo_order_seed_o{o.id}")
                db.add(p)
                db.flush()
                pay.fulfil(db, p, f"demo_pay_seed_o{o.id}")
            now = utcnow()
            if status in ("delivered", "completed"):
                o.status, o.delivered_at, o.delivery_note = "delivered", now, "Delivered: files and handover notes attached."
            if status == "completed":
                o.status, o.completed_at, o.payout_status = "completed", now, "pending"
            db.commit()
            if status == "completed":
                payouts.release(db, o)
            return o
        order("priya@technova.in", "sneha.iyer@mail.com", jobs[1].title, 120000, "in_progress",
              job_id=jobs[1].id, proposal_id=p_hire.id)
        svc = services["Power BI finance dashboard (P&L, cash flow)"]
        order("neha@finedge.com", "fatima.khan@mail.com", svc.title, svc.price, "completed", service_id=svc.id,
              requirements="Monthly P&L and cash-flow views for the board pack.")
        svc = services["CI/CD pipeline and Kubernetes deploy for one service"]
        order("neha@finedge.com", "rohan.das@mail.com", svc.title, svc.price, "delivered", service_id=svc.id)
        svc = services["Code review and performance audit of a Python service"]
        order("priya@technova.in", "rahul.verma@mail.com", svc.title, svc.price, "pending_payment", service_id=svc.id)
        # reviews on the completed order, and a client ↔ freelancer conversation
        from app.models import Review, Conversation, Message
        from app.api.v1.endpoints.reviews import _recompute
        done = db.query(Order).filter(Order.status == "completed").first()
        if done:
            db.add(Review(order_id=done.id, reviewer_user_id=done.client.owner_user_id, reviewee_role="freelancer",
                          consultant_id=done.consultant_id, rating=5,
                          comment="Clear dashboards, delivered early, and explained everything to our CFO."))
            db.add(Review(order_id=done.id, reviewer_user_id=done.consultant.user_id, reviewee_role="client",
                          client_id=done.client_id, rating=5, comment="Precise brief and quick feedback."))
            db.flush()
            _recompute(db, done.consultant_id, done.client_id)
        conv = Conversation(client_id=clients["priya@technova.in"].id, consultant_id=freelancers["rahul.verma@mail.com"].id,
                            job_id=jobs[0].id)
        db.add(conv)
        db.flush()
        t0 = utcnow() - dt.timedelta(hours=3)
        for i, (who, body) in enumerate([
                ("client", "Hi Rahul — your proposal looks great. Could you start on the 1st?"),
                ("freelancer", "Yes, the 1st works. I'd begin with the tenant data model and auth."),
                ("client", "Perfect. I've attached the full JD to the job. Talk soon!")]):
            uid = clients["priya@technova.in"].owner_user_id if who == "client" else freelancers["rahul.verma@mail.com"].user_id
            db.add(Message(conversation_id=conv.id, sender_user_id=uid, body=body, created_at=t0 + dt.timedelta(minutes=20 * i)))
        conv.last_message_at = t0 + dt.timedelta(minutes=40)
        conv.client_read_at = conv.last_message_at
        db.commit()
        print(f"Demo data ready: {db.query(User).count()} users, {db.query(Job).count()} jobs, "
              f"{db.query(Service).count()} services, {db.query(Order).count()} orders.")
        print(f"  Admin:      {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print(f"  Client:     priya@technova.in / {DEMO_PASSWORD}")
        print(f"  Freelancer: rahul.verma@mail.com / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
