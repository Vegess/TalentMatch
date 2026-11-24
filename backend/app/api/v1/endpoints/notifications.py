from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Notification, User
from app.models._time import utcnow

router = APIRouter()


def n_out(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
            "read": n.read_at is not None, "created_at": n.created_at}


@router.get("", summary="My notifications, newest first")
def list_notifications(limit: int = Query(30, ge=1, le=100), user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(limit).all()
    unread = db.query(Notification).filter(Notification.user_id == user.id, Notification.read_at.is_(None)).count()
    return {"unread": unread, "items": [n_out(n) for n in rows]}


@router.post("/{notification_id}/read", summary="Mark one as read")
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read_at = n.read_at or utcnow()
    db.commit()
    return n_out(n)


@router.post("/read-all", summary="Mark all as read")
def mark_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.user_id == user.id, Notification.read_at.is_(None)) \
        .update({Notification.read_at: utcnow()})
    db.commit()
    return {"marked": n}
