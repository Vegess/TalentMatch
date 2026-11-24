"""In-app notifications (+ email). Each call stores a Notification, returns a realtime event, and emails the user
if they allow it. Callers publish the returned events with realtime.publish_all."""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models import Notification, User
from app.services import email


def notify(db: Session, user_id: Optional[int], kind: str, title: str, body: str = "", link: Optional[str] = None,
           send_email: bool = True, commit: bool = True) -> List[Dict[str, Any]]:
    if not user_id:
        return []
    u = db.get(User, user_id)
    if not u or not u.is_active:
        return []
    n = Notification(user_id=u.id, kind=kind, title=title[:200], body=(body or "")[:1000] or None, link=link)
    db.add(n)
    if commit:
        db.commit()
        db.refresh(n)
    else:
        db.flush()
    if send_email and u.email_notifications:
        email.send(u.email, title, email.wrap(u.name, body or title, link))
    return [{"type": "notification", "id": n.id, "kind": kind, "title": n.title, "body": n.body, "link": link,
             "user_ids": [u.id], "admins": False}]
