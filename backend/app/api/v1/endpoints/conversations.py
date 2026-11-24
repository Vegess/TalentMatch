"""Private messages between a client company and a freelancer.

Who can start a thread:
- a client on a paid plan can message any public freelancer;
- on the FREE plan, only freelancers who applied to one of the client's jobs or have an order with them;
- a freelancer can message a client they applied to or have an order with.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.plans import plan_limits
from app.core.ratelimit import check
from app.models import Conversation, Message, Client, Consultant, Proposal, Order, Job, User
from app.models._time import utcnow
from app.services import subscriptions as subs
from app.services.notify import notify
from app.services.realtime import publish_all

router = APIRouter()


class StartIn(BaseModel):
    consultant_id: Optional[int] = None  # when a client starts
    client_id: Optional[int] = None      # when a freelancer starts
    job_id: Optional[int] = None
    body: Optional[str] = Field(None, max_length=4000)


class MessageIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


def _have_relationship(db: Session, client_id: int, consultant_id: int) -> bool:
    applied = db.query(Proposal).join(Job, Job.id == Proposal.job_id).filter(
        Job.client_id == client_id, Proposal.consultant_id == consultant_id).first()
    ordered = db.query(Order).filter(Order.client_id == client_id, Order.consultant_id == consultant_id).first()
    return bool(applied or ordered)


def _side(user: User, conv: Conversation) -> Optional[str]:
    if conv.client and conv.client.owner_user_id == user.id:
        return "client"
    if conv.consultant and conv.consultant.user_id == user.id:
        return "freelancer"
    return None


def _get(db: Session, cid: int, user: User) -> tuple[Conversation, str]:
    conv = db.get(Conversation, cid)
    side = _side(user, conv) if conv else None
    if not side:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv, side


def _unread(db: Session, conv: Conversation, side: str) -> int:
    read_at = conv.client_read_at if side == "client" else conv.freelancer_read_at
    q = db.query(Message).filter(Message.conversation_id == conv.id)
    me = conv.client.owner_user_id if side == "client" else conv.consultant.user_id
    q = q.filter(Message.sender_user_id != me)
    if read_at:
        q = q.filter(Message.created_at > read_at)
    return q.count()


def conv_out(db: Session, conv: Conversation, side: str) -> dict:
    last = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.id.desc()).first()
    other = ({"type": "freelancer", "id": conv.consultant.id, "name": conv.consultant.name,
              "subtitle": conv.consultant.headline} if side == "client" else
             {"type": "client", "id": conv.client.id, "name": conv.client.company_name or conv.client.name,
              "subtitle": conv.client.industry})
    return {"id": conv.id, "other": other, "job": {"id": conv.job.id, "title": conv.job.title} if conv.job else None,
            "last_message": {"body": last.body[:160], "created_at": last.created_at,
                             "mine": last.sender_user_id == (conv.client.owner_user_id if side == "client" else conv.consultant.user_id)}
            if last else None,
            "last_message_at": conv.last_message_at, "unread": _unread(db, conv, side), "my_side": side}


def msg_out(m: Message, me: int) -> dict:
    return {"id": m.id, "body": m.body, "created_at": m.created_at, "mine": m.sender_user_id == me,
            "sender_name": m.sender.name if m.sender else None}


async def _post(db: Session, conv: Conversation, side: str, user: User, body: str) -> Message:
    check(f"msg:{user.id}", 30, 60)
    m = Message(conversation_id=conv.id, sender_user_id=user.id, body=body.strip())
    db.add(m)
    conv.last_message_at = m.created_at = utcnow()
    if side == "client":
        conv.client_read_at = m.created_at
        recipient = conv.consultant.user_id
    else:
        conv.freelancer_read_at = m.created_at
        recipient = conv.client.owner_user_id
    # Email only for the first unread message, so a burst of messages doesn't flood the inbox.
    already_unread = _unread(db, conv, "freelancer" if side == "client" else "client") > 0
    db.commit()
    db.refresh(m)
    sender = (conv.client.company_name or conv.client.name) if side == "client" else conv.consultant.name
    events = [{"type": "message", "conversation_id": conv.id, "message": {**msg_out(m, -1)}, "user_ids": [recipient] if recipient else [],
               "admins": False}]
    events += notify(db, recipient, "message", f"New message from {sender}", body[:300],
                     f"/messages/{conv.id}", send_email=not already_unread)
    await publish_all(events)
    return m


@router.get("", summary="My conversations, newest first")
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "client":
        c = db.query(Client).filter(Client.owner_user_id == user.id).first()
        rows = db.query(Conversation).filter(Conversation.client_id == (c.id if c else -1))
        side = "client"
    elif user.role == "freelancer":
        c = db.query(Consultant).filter(Consultant.user_id == user.id).first()
        rows = db.query(Conversation).filter(Conversation.consultant_id == (c.id if c else -1))
        side = "freelancer"
    else:
        return []
    rows = rows.order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc()).limit(200).all()
    return [conv_out(db, cv, side) for cv in rows]


@router.post("", summary="Start (or reopen) a conversation")
async def start(payload: StartIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "client":
        client = db.query(Client).filter(Client.owner_user_id == user.id).first()
        consultant = db.get(Consultant, payload.consultant_id or 0)
        if not client or not consultant or not consultant.is_public or not consultant.user_id:
            raise HTTPException(status_code=404, detail="Freelancer not found")
        if not _have_relationship(db, client.id, consultant.id):
            sub = subs.get_active(db, client.id)
            if not sub or not plan_limits(sub.plan_type).get("can_message_any"):
                raise HTTPException(status_code=403, detail="On the Free plan you can message freelancers who applied "
                                                            "to your jobs. Upgrade to message anyone.")
    elif user.role == "freelancer":
        consultant = db.query(Consultant).filter(Consultant.user_id == user.id).first()
        client = db.get(Client, payload.client_id or 0)
        if not consultant or not client or not _have_relationship(db, client.id, consultant.id):
            raise HTTPException(status_code=403, detail="You can message clients you've applied to or worked with.")
    else:
        raise HTTPException(status_code=403, detail="Admins can't start conversations")
    conv = db.query(Conversation).filter(Conversation.client_id == client.id,
                                         Conversation.consultant_id == consultant.id).first()
    if not conv:
        job = db.get(Job, payload.job_id) if payload.job_id else None
        conv = Conversation(client_id=client.id, consultant_id=consultant.id,
                            job_id=job.id if job and job.client_id == client.id else None)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    side = "client" if user.role == "client" else "freelancer"
    if payload.body and payload.body.strip():
        await _post(db, conv, side, user, payload.body)
    return conv_out(db, conv, side)


@router.get("/unread-count", summary="Unread messages across all my conversations")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"unread": sum(c["unread"] for c in list_conversations(user, db))}


@router.get("/{conversation_id}", summary="One conversation with its messages (marks them read)")
def get_conversation(conversation_id: int, after_id: int = Query(0, ge=0), user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    conv, side = _get(db, conversation_id, user)
    msgs = db.query(Message).filter(Message.conversation_id == conv.id, Message.id > after_id) \
        .order_by(Message.id).limit(500).all()
    if side == "client":
        conv.client_read_at = utcnow()
    else:
        conv.freelancer_read_at = utcnow()
    db.commit()
    return {**conv_out(db, conv, side), "messages": [msg_out(m, user.id) for m in msgs]}


@router.post("/{conversation_id}/messages", summary="Send a message")
async def send(conversation_id: int, payload: MessageIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    conv, side = _get(db, conversation_id, user)
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Message is empty")
    m = await _post(db, conv, side, user, payload.body)
    return msg_out(m, user.id)
