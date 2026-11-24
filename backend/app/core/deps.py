from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User, Client, Consultant


def _token_from(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = _token_from(request)
    if not token:
        return None
    data = decode_access_token(token)
    if not data:
        return None
    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active:
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _token_from(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in", headers={"WWW-Authenticate": "Bearer"})
    data = decode_access_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Session expired", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled or removed")
    return user


def require_roles(*roles: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You don't have access to this")
        return user
    return dep


require_admin = require_roles("admin")


def current_client(user: User = Depends(require_roles("client")), db: Session = Depends(get_db)) -> Client:
    c = db.query(Client).filter(Client.owner_user_id == user.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="No company profile for this account")
    return c


def current_freelancer(user: User = Depends(require_roles("freelancer")), db: Session = Depends(get_db)) -> Consultant:
    c = db.query(Consultant).filter(Consultant.user_id == user.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="No freelancer profile for this account")
    return c
