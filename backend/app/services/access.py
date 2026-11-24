"""Ownership checks. Every write goes through one of these so tenants can't touch each other's data."""
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User, Job, Service, Order, Consultant, Client


def is_admin(u: Optional[User]) -> bool:
    return bool(u and u.role == "admin")


def owns_job(db: Session, u: Optional[User], job: Job) -> bool:
    return bool(u) and (is_admin(u) or (job.client is not None and job.client.owner_user_id == u.id))


def owns_consultant(u: Optional[User], c: Consultant) -> bool:
    return bool(u) and (is_admin(u) or c.user_id == u.id)


def owns_service(u: Optional[User], s: Service) -> bool:
    return bool(u) and (is_admin(u) or (s.consultant is not None and s.consultant.user_id == u.id))


def order_party(u: Optional[User], o: Order) -> Optional[str]:
    """'client' | 'freelancer' | 'admin' | None"""
    if not u:
        return None
    if is_admin(u):
        return "admin"
    if o.client and o.client.owner_user_id == u.id:
        return "client"
    if o.consultant and o.consultant.user_id == u.id:
        return "freelancer"
    return None


def get_owner(db: Session, owner_type: str, owner_id: int):
    model = {"job": Job, "consultant": Consultant, "service": Service, "order": Order}.get(owner_type)
    obj = db.get(model, owner_id) if model else None
    if not obj:
        raise HTTPException(status_code=404, detail=f"{owner_type.capitalize()} not found")
    return obj


def can_write_attachments(db: Session, u: User, owner_type: str, obj) -> bool:
    if owner_type == "job":
        return owns_job(db, u, obj)
    if owner_type == "consultant":
        return owns_consultant(u, obj)
    if owner_type == "service":
        return owns_service(u, obj)
    if owner_type == "order":
        return order_party(u, obj) is not None
    return False


def can_read_attachments(db: Session, u: User, owner_type: str, obj) -> bool:
    if can_write_attachments(db, u, owner_type, obj):
        return True
    if owner_type == "job":
        return obj.status == "open"
    if owner_type == "consultant":
        return bool(obj.is_public)
    if owner_type == "service":
        return obj.status == "active"
    return False  # orders: only the two parties and admins
