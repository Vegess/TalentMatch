from typing import Optional, Any, Dict
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.ratelimit import client_ip
from app.models import AuditLog


def log(db: Session, action: str, actor_id: Optional[int] = None, target_type: Optional[str] = None,
        target_id: Optional[int] = None, details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None, commit: bool = True):
    db.add(AuditLog(actor_user_id=actor_id, action=action, target_type=target_type, target_id=target_id,
                    details=details, ip=client_ip(request) if request else None))
    if commit:
        db.commit()
