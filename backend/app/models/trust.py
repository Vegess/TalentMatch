from sqlalchemy import (Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint, SmallInteger)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow


class Review(Base):
    """A rating left after a completed order. Each side (client, freelancer) can review once per order."""
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("order_id", "reviewer_user_id", name="uq_review_order_reviewer"),)

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    reviewer_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewee_role = Column(String(10), nullable=False)  # freelancer | client
    consultant_id = Column(Integer, ForeignKey("consultants.id", ondelete="CASCADE"), index=True, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    rating = Column(SmallInteger, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    order = relationship("Order")
    reviewer = relationship("User")


class Conversation(Base):
    """A private thread between one client company and one freelancer."""
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("client_id", "consultant_id", name="uq_conversation_pair"),)

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    consultant_id = Column(Integer, ForeignKey("consultants.id", ondelete="CASCADE"), index=True, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    last_message_at = Column(DateTime, nullable=True, index=True)
    client_read_at = Column(DateTime, nullable=True)
    freelancer_read_at = Column(DateTime, nullable=True)

    client = relationship("Client")
    consultant = relationship("Consultant")
    job = relationship("Job")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan",
                            order_by="Message.id")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    sender_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind = Column(String(40), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(String(1000), nullable=True)
    link = Column(String(300), nullable=True)
    read_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)


class PasswordReset(Base):
    """Single-use reset link. Only the SHA-256 of the token is stored."""
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
