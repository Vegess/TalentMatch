from sqlalchemy import Column, Integer, String, Text, Float, JSON, DateTime, Boolean, ForeignKey, SmallInteger
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow


class Consultant(Base):
    """A freelancer profile. Owned by one user with role 'freelancer' (or created by an admin)."""
    __tablename__ = "consultants"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True)
    name = Column(String(120), nullable=False, index=True)
    email = Column(String(254), unique=True, index=True, nullable=False)
    phone = Column(String(40), nullable=True)
    headline = Column(String(160), nullable=True)
    bio = Column(Text, nullable=True)
    location = Column(String(120), nullable=True)
    hourly_rate = Column(Integer, nullable=True)  # INR
    availability = Column(String(20), nullable=False, default="available")  # available | busy
    links = Column(JSON, nullable=False, default=list)  # [{"label": "GitHub", "url": "https://..."}]
    extracted_text = Column(Text, nullable=True)
    skills = Column(JSON, nullable=False, default=list)
    experience_years = Column(Float, nullable=False, default=0.0)
    source = Column(String(20), nullable=False, default="manual")  # manual | pdf | signup
    is_public = Column(Boolean, nullable=False, default=True)
    # Location & working hours (hours are 0-23 in the freelancer's own timezone)
    country = Column(String(2), nullable=True, index=True)
    timezone = Column(String(64), nullable=True)
    work_start_hour = Column(SmallInteger, nullable=True)
    work_end_hour = Column(SmallInteger, nullable=True)
    languages = Column(JSON, nullable=False, default=list, server_default="[]")
    currency = Column(String(3), nullable=False, default="INR", server_default="INR")  # for rates & services
    # Trust
    verified_at = Column(DateTime, nullable=True)
    rating_avg = Column(Float, nullable=True)
    rating_count = Column(Integer, nullable=False, default=0, server_default="0")
    # Payouts (Razorpay Route linked account). Full bank account numbers are never stored.
    payout_account_id = Column(String(40), nullable=True)      # acc_xxx
    payout_method = Column(String(20), nullable=True)          # bank_account | upi
    payout_masked = Column(String(80), nullable=True)          # e.g. "HDFC0000317 · ••••3456" or the UPI ID
    payout_beneficiary = Column(String(200), nullable=True)
    payout_status = Column(String(30), nullable=False, default="not_set")  # not_set|under_review|active|needs_clarification|failed
    payout_note = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="consultant")
    matches = relationship("Match", back_populates="consultant", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="consultant", cascade="all, delete-orphan")
    proposals = relationship("Proposal", back_populates="consultant", cascade="all, delete-orphan")
