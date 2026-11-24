import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import limit
from app.core.security import (hash_password, verify_password, password_problem, create_access_token,
                               new_refresh_token, sha256)
from app.models import User, AuthSession, Client, Consultant, PasswordReset
from app.models._time import utcnow
from app.schemas.auth import RegisterIn, LoginIn, ChangePasswordIn, PreferencesIn, ForgotPasswordIn, ResetPasswordIn
from app.services import audit, subscriptions as subs

router = APIRouter()


def user_out(db: Session, u: User) -> dict:
    out = {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "is_active": u.is_active,
           "created_at": u.created_at, "client_id": None, "consultant_id": None, "plan": None,
           "preferred_language": u.preferred_language or "en", "email_notifications": bool(u.email_notifications),
           "currency": None}
    if u.role == "client":
        c = db.query(Client).filter(Client.owner_user_id == u.id).first()
        if c:
            out["client_id"] = c.id
            out["company_name"] = c.company_name
            out["plan"] = subs.current_plan(db, c.id)
            out["currency"] = c.currency
    elif u.role == "freelancer":
        c = db.query(Consultant).filter(Consultant.user_id == u.id).first()
        if c:
            out["consultant_id"] = c.id
            out["currency"] = c.currency
    return out


def _set_cookie(response: Response, raw: str, max_age_s: int):
    response.set_cookie(config.REFRESH_COOKIE_NAME, raw, max_age=max_age_s, httponly=True,
                        secure=config.COOKIE_SECURE, samesite=config.COOKIE_SAMESITE, path="/api/v1/auth")


def _clear_cookie(response: Response):
    response.delete_cookie(config.REFRESH_COOKIE_NAME, path="/api/v1/auth",
                           secure=config.COOKIE_SECURE, samesite=config.COOKIE_SAMESITE, httponly=True)


def _start_session(db: Session, user: User, request: Request, response: Response) -> dict:
    raw, h = new_refresh_token()
    now = utcnow()
    s = AuthSession(user_id=user.id, token_hash=h, created_at=now,
                    expires_at=now + dt.timedelta(days=config.REFRESH_SLIDING_DAYS),
                    absolute_expires_at=now + dt.timedelta(days=config.REFRESH_ABSOLUTE_DAYS),
                    user_agent=(request.headers.get("user-agent") or "")[:300])
    db.add(s)
    user.last_login_at = now
    db.commit()
    _set_cookie(response, raw, config.REFRESH_SLIDING_DAYS * 86400)
    return _token_payload(db, user)


def _token_payload(db: Session, user: User) -> dict:
    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer",
            "expires_in": config.ACCESS_TOKEN_MINUTES * 60, "user": user_out(db, user)}


def create_user(db: Session, *, role: str, name: str, email: str, password: str,
                company_name: Optional[str] = None, headline: Optional[str] = None,
                country: Optional[str] = None, timezone: Optional[str] = None, language: Optional[str] = None) -> User:
    """Create a user plus their company (client) or profile (freelancer). Used by signup, seed and tests."""
    email = email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    problem = password_problem(password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    from app.core.geo import COUNTRY_CODES, valid_timezone, default_currency
    country = (country or "").upper() or None
    country = country if country in COUNTRY_CODES else None
    timezone = timezone if timezone and valid_timezone(timezone) else None
    user = User(email=email, name=name.strip(), password_hash=hash_password(password), role=role,
                preferred_language=language or "en")
    db.add(user)
    db.flush()
    if role == "client":
        if db.query(Client).filter(Client.email == email).first():
            raise HTTPException(status_code=400, detail="An account with this email already exists")
        # Every signup creates its OWN company, even if the name matches an existing one.
        client = Client(owner_user_id=user.id, name=user.name, email=email,
                        company_name=(company_name or "").strip() or None, country=country, timezone=timezone,
                        currency=default_currency(country))
        db.add(client)
        db.flush()
        subs.start_subscription(db, client.id, "FREE", commit=False)
    elif role == "freelancer":
        existing = db.query(Consultant).filter(Consultant.email == email).first()
        if existing and existing.user_id is None:
            existing.user_id = user.id  # claim a profile an admin created for this email
        elif existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists")
        else:
            db.add(Consultant(user_id=user.id, name=user.name, email=email,
                              headline=(headline or "").strip() or None, source="signup", skills=[], links=[],
                              country=country, timezone=timezone, currency=default_currency(country), languages=[]))
    db.commit()
    db.refresh(user)
    return user


@router.post("/register", summary="Sign up as a client (company) or freelancer",
             dependencies=[Depends(limit("register", 10, 3600))])
def register(payload: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if config.SIGNUP_MODE != "open":
        raise HTTPException(status_code=403, detail="Sign-ups are closed right now.")
    try:
        user = create_user(db, role=payload.role, name=payload.name, email=payload.email,
                           password=payload.password, company_name=payload.company_name,
                           headline=payload.headline, country=payload.country, timezone=payload.timezone,
                           language=payload.language)
    except HTTPException:
        db.rollback()
        raise
    audit.log(db, "user.register", user.id, "user", user.id, {"role": user.role}, request)
    return _start_session(db, user, request, response)


@router.post("/login", summary="Sign in", dependencies=[Depends(limit("login", 10, 300))])
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been disabled. Contact support.")
    audit.log(db, "user.login", user.id, "user", user.id, None, request)
    return _start_session(db, user, request, response)


@router.post("/refresh", summary="Get a new access token using the refresh cookie (rotates the cookie)",
             dependencies=[Depends(limit("refresh", 60, 60))])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(config.REFRESH_COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="Not signed in")
    s = db.query(AuthSession).filter(AuthSession.token_hash == sha256(raw)).first()
    now = utcnow()
    if not s:
        _clear_cookie(response)
        raise HTTPException(status_code=401, detail="Not signed in")
    if s.revoked_at is not None:
        # A rotated-out token was used again: likely stolen. End every session for this user.
        db.query(AuthSession).filter(AuthSession.user_id == s.user_id, AuthSession.revoked_at.is_(None)) \
            .update({AuthSession.revoked_at: now})
        db.commit()
        audit.log(db, "session.reuse_detected", s.user_id, "user", s.user_id, None, request)
        _clear_cookie(response)
        raise HTTPException(status_code=401, detail="Session ended. Please sign in again.")
    if s.expires_at <= now or s.absolute_expires_at <= now or not s.user.is_active:
        s.revoked_at = now
        db.commit()
        _clear_cookie(response)
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    # rotate
    s.revoked_at = now
    new_raw, new_hash = new_refresh_token()
    expires = min(now + dt.timedelta(days=config.REFRESH_SLIDING_DAYS), s.absolute_expires_at)
    db.add(AuthSession(user_id=s.user_id, token_hash=new_hash, created_at=now, expires_at=expires,
                       absolute_expires_at=s.absolute_expires_at, user_agent=s.user_agent))
    db.commit()
    _set_cookie(response, new_raw, int((expires - now).total_seconds()))
    return _token_payload(db, s.user)


@router.post("/logout", summary="Sign out this device")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(config.REFRESH_COOKIE_NAME)
    if raw:
        s = db.query(AuthSession).filter(AuthSession.token_hash == sha256(raw)).first()
        if s and s.revoked_at is None:
            s.revoked_at = utcnow()
            db.commit()
    _clear_cookie(response)
    return {"status": "signed_out"}


@router.post("/logout-all", summary="Sign out everywhere")
def logout_all(request: Request, response: Response, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    n = db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)) \
        .update({AuthSession.revoked_at: utcnow()})
    db.commit()
    audit.log(db, "user.logout_all", user.id, "user", user.id, {"sessions": n}, request)
    _clear_cookie(response)
    return {"status": "signed_out", "sessions_ended": n}


@router.get("/me", summary="The signed-in user")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_out(db, user)


@router.post("/change-password", summary="Change password (signs out other devices)")
def change_password(payload: ChangePasswordIn, request: Request, response: Response,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is wrong")
    problem = password_problem(payload.new_password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    user.password_hash = hash_password(payload.new_password)
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)) \
        .update({AuthSession.revoked_at: utcnow()})
    db.commit()
    audit.log(db, "user.change_password", user.id, "user", user.id, None, request)
    return _start_session(db, user, request, response)


@router.patch("/me", summary="Update my preferences (language, email notifications)")
def update_me(payload: PreferencesIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for k, v in payload.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(user, k, v)
    db.commit()
    return user_out(db, user)


FORGOT_REPLY = {"status": "ok", "message": "If an account exists for that email, a reset link is on its way."}


@router.post("/forgot-password", summary="Email a password-reset link (same reply whether or not the email exists)",
             dependencies=[Depends(limit("forgot", 5, 3600))])
def forgot_password(payload: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    from app.services import email
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user and user.is_active:
        now = utcnow()
        db.query(PasswordReset).filter(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)) \
            .update({PasswordReset.used_at: now})  # only the newest link works
        raw, h = new_refresh_token()
        db.add(PasswordReset(user_id=user.id, token_hash=h, created_at=now,
                             expires_at=now + dt.timedelta(minutes=config.PASSWORD_RESET_MINUTES)))
        db.commit()
        email.send(user.email, "Reset your TalentMatch password", email.wrap(
            user.name, f"Someone asked to reset your password. The link below works once and expires in "
                       f"{config.PASSWORD_RESET_MINUTES} minutes. If it wasn't you, ignore this email.",
            f"/reset-password?token={raw}"))
        audit.log(db, "user.forgot_password", user.id, "user", user.id, None, request)
    return FORGOT_REPLY


@router.post("/reset-password", summary="Set a new password with a reset link (signs out every device)",
             dependencies=[Depends(limit("reset", 10, 3600))])
def reset_password(payload: ResetPasswordIn, request: Request, response: Response, db: Session = Depends(get_db)):
    pr = db.query(PasswordReset).filter(PasswordReset.token_hash == sha256(payload.token)).first()
    now = utcnow()
    if not pr or pr.used_at is not None or pr.expires_at <= now:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Ask for a new one.")
    problem = password_problem(payload.new_password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    user = db.get(User, pr.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Ask for a new one.")
    user.password_hash = hash_password(payload.new_password)
    pr.used_at = now
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)) \
        .update({AuthSession.revoked_at: now})
    db.commit()
    audit.log(db, "user.reset_password", user.id, "user", user.id, None, request)
    return _start_session(db, user, request, response)
