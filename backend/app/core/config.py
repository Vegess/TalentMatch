"""Central configuration. Every value can be overridden with an environment variable."""
import os
import secrets


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


ENV = os.getenv("ENV", "development")  # "development" | "production"
IS_PROD = ENV == "production"

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URL") or "sqlite:///./talentmatch.db"
# Neon / Render give "postgres://" or "postgresql://"; SQLAlchemy needs the driver name.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgresql://"):]

# ---- Auth -------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(48)  # set it in production!
ACCESS_TOKEN_MINUTES = int(_float("ACCESS_TOKEN_MINUTES", 30))
REFRESH_SLIDING_DAYS = int(_float("REFRESH_SLIDING_DAYS", 30))
REFRESH_ABSOLUTE_DAYS = int(_float("REFRESH_ABSOLUTE_DAYS", 90))
REFRESH_COOKIE_NAME = "tm_refresh"
# Frontend on Vercel + API on Render are different sites → cookie must be SameSite=None; Secure.
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "none" if IS_PROD else "lax")
COOKIE_SECURE = _bool("COOKIE_SECURE", IS_PROD)
SIGNUP_MODE = os.getenv("SIGNUP_MODE", "open")  # "open" | "closed"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# ---- Matching -----------------------------------------------------------------
MATCH_THRESHOLD = _float("MATCH_THRESHOLD", 50.0)
SKILL_WEIGHT = _float("SKILL_WEIGHT", 0.7)
EXPERIENCE_WEIGHT = _float("EXPERIENCE_WEIGHT", 0.3)
DEFAULT_RANKING_PLUGIN = "app.plugins.ranking.standard_weighted"
DEFAULT_PDF_PLUGIN = "app.plugins.ingestion.standard_pdf"

# ---- Documents ----------------------------------------------------------------
MAX_UPLOAD_MB = _float("MAX_UPLOAD_MB", 10.0)
ALLOWED_UPLOAD_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

# ---- Payments -----------------------------------------------------------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
# "razorpay" when keys are set, otherwise "demo" (simulated checkout, no money moves).
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER") or ("razorpay" if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET else "demo")
PLATFORM_FEE_PERCENT = _float("PLATFORM_FEE_PERCENT", 10.0)
# Razorpay Route (automatic freelancer payouts). Must also be enabled on your Razorpay account.
RAZORPAY_ROUTE_ENABLED = _bool("RAZORPAY_ROUTE_ENABLED", False)
CURRENCY = "INR"

# ---- Stripe (international payments: USD / EUR / GBP) ----------------------------
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
CURRENCIES = ("INR", "USD", "EUR", "GBP")

# ---- Email (SMTP). Without SMTP_HOST, emails are written to the server log instead. -------------
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(_float("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_TLS = _bool("SMTP_TLS", True)
EMAIL_FROM = os.getenv("EMAIL_FROM", "TalentMatch <no-reply@talentmatch.local>")
PASSWORD_RESET_MINUTES = int(_float("PASSWORD_RESET_MINUTES", 30))

# ---- HTTP ---------------------------------------------------------------------
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")
