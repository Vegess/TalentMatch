from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow


class Client(Base):
    """A hiring company. Owned by one user with role 'client'."""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True)
    name = Column(String(120), nullable=False)          # contact name
    email = Column(String(254), unique=True, index=True, nullable=False)
    company_name = Column(String(200), nullable=True)
    website = Column(String(500), nullable=True)
    industry = Column(String(120), nullable=True)
    about = Column(Text, nullable=True)
    country = Column(String(2), nullable=True)
    timezone = Column(String(64), nullable=True)
    currency = Column(String(3), nullable=False, default="INR", server_default="INR")  # billing currency
    verified_at = Column(DateTime, nullable=True)
    rating_avg = Column(Float, nullable=True)
    rating_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, nullable=False, default=utcnow)

    owner = relationship("User", back_populates="client")
    jobs = relationship("Job", back_populates="client", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="client", cascade="all, delete-orphan",
                                 order_by="Subscription.id")
