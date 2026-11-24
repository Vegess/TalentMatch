import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core import config
from app.core.database import run_migrations, SessionLocal
from app.core.plugin_loader import PluginLoader
from app.api.v1.endpoints import (auth, freelancers, clients, jobs, proposals, services, orders, payments,
                                  subscriptions, documents, admin, tools, websockets,
                                  reviews, conversations, notifications)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.getenv("FRONTEND_DIR") or os.path.abspath(os.path.join(_BACKEND_DIR, "..", "frontend", "dist"))


def _bootstrap_admin():
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD if no such user exists."""
    if not (config.ADMIN_EMAIL and config.ADMIN_PASSWORD):
        return
    from app.core.security import hash_password
    from app.models import User
    db = SessionLocal()
    try:
        email = config.ADMIN_EMAIL.lower()
        if not db.query(User).filter(User.email == email).first():
            db.add(User(email=email, name="Administrator", role="admin",
                        password_hash=hash_password(config.ADMIN_PASSWORD)))
            db.commit()
            print(f"[startup] created admin {email}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_migrations()
    PluginLoader().load_plugins()
    _bootstrap_admin()
    from app.services import matching, subscriptions as subs
    db = SessionLocal()
    try:
        subs.expire_old(db)
        matching.rematch_all(db)  # keep matches consistent with the current threshold/weights
    finally:
        db.close()
    if config.SECRET_KEY and not os.getenv("SECRET_KEY") and config.IS_PROD:
        print("[startup] WARNING: SECRET_KEY is not set; everyone is signed out on each restart.")
    print(f"\n  >>> App:      http://localhost:8000/\n  >>> API docs: http://localhost:8000/docs\n"
          f"  >>> Payments: {config.PAYMENT_PROVIDER}\n")
    yield


app = FastAPI(
    title="TalentMatch API",
    version="3.0.0",
    description="Freelance marketplace: clients subscribe and post job descriptions, freelancers publish profiles "
                "and services, the platform ranks fit, takes payments via Razorpay and runs a control room.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


API = "/api/v1"
app.include_router(auth.router, prefix=f"{API}/auth", tags=["auth"])
app.include_router(freelancers.router, prefix=f"{API}/freelancers", tags=["freelancers"])
app.include_router(clients.router, prefix=f"{API}/clients", tags=["clients"])
app.include_router(jobs.router, prefix=f"{API}/jobs", tags=["jobs"])
app.include_router(proposals.router, prefix=f"{API}/proposals", tags=["proposals"])
app.include_router(services.router, prefix=f"{API}/services", tags=["services"])
app.include_router(orders.router, prefix=f"{API}/orders", tags=["orders"])
app.include_router(payments.router, prefix=f"{API}/payments", tags=["payments"])
app.include_router(subscriptions.router, prefix=f"{API}/subscriptions", tags=["subscriptions"])
app.include_router(documents.router, prefix=f"{API}/documents", tags=["documents"])
app.include_router(reviews.router, prefix=f"{API}/reviews", tags=["reviews"])
app.include_router(conversations.router, prefix=f"{API}/conversations", tags=["messages"])
app.include_router(notifications.router, prefix=f"{API}/notifications", tags=["notifications"])
app.include_router(admin.router, prefix=f"{API}/admin", tags=["control room"])
app.include_router(tools.router, prefix=f"{API}/admin/tools", tags=["control room"])
app.include_router(websockets.router, tags=["realtime"])


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "version": app.version, "payments": config.PAYMENT_PROVIDER}


# ---- Single-page app (built React frontend) ----------------------------------------------------
@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith(("api/", "ws")) or full_path in ("docs", "redoc", "openapi.json"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    index = os.path.join(FRONTEND_DIST, "index.html")
    if not os.path.isfile(index):
        return JSONResponse({"detail": "Frontend not built. Run `npm run build` in frontend/, or open /docs."},
                            status_code=404)
    candidate = os.path.abspath(os.path.join(FRONTEND_DIST, full_path))
    if full_path and candidate.startswith(FRONTEND_DIST + os.sep) and os.path.isfile(candidate):
        headers = {"Cache-Control": "public, max-age=31536000, immutable"} if "/assets/" in candidate else None
        return FileResponse(candidate, headers=headers)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
