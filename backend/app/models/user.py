from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow

ROLES = ("admin", "client", "freelancer")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(254), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, index=True)  # admin | client | freelancer
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    last_login_at = Column(DateTime, nullable=True)
    preferred_language = Column(String(5), nullable=False, default="en", server_default="en")
    email_notifications = Column(Boolean, nullable=False, default=True, server_default="1")

    sessions = relationship("AuthSession", back_populates="user", cascade="all, delete-orphan")
    client = relationship("Client", back_populates="owner", uselist=False)
    consultant = relationship("Consultant", back_populates="user", uselist=False)


class AuthSession(Base):
    """A signed-in device. Only the SHA-256 of the refresh token is stored."""
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    expires_at = Column(DateTime, nullable=False)           # sliding expiry
    absolute_expires_at = Column(DateTime, nullable=False)  # hard limit
    revoked_at = Column(DateTime, nullable=True)
    user_agent = Column(String(300), nullable=True)

    user = relationship("User", back_populates="sessions")
