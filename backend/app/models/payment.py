from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow


class Payment(Base):
    """One checkout attempt. Amounts are in minor units (paise / cents) to avoid rounding errors.
    `amount_paise` keeps its historical name but holds minor units of `currency`."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), index=True, nullable=True)
    purpose = Column(String(20), nullable=False)  # subscription | order
    plan_type = Column(String(20), nullable=True)
    months = Column(Integer, nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_paise = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    provider = Column(String(20), nullable=False)  # razorpay | stripe | demo
    provider_order_id = Column(String(255), unique=True, index=True, nullable=False)  # Razorpay order / Stripe session
    provider_payment_id = Column(String(64), nullable=True)
    status = Column(String(10), nullable=False, default="created", index=True)  # created | paid | failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User")
    client = relationship("Client")
    order = relationship("Order")
