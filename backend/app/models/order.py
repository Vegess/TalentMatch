from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow

ORDER_STATUSES = ("pending_payment", "in_progress", "delivered", "completed", "cancelled")


class Order(Base):
    """Work a client pays for: a bought service, or an accepted job proposal.

    With Razorpay Route, the freelancer's share is transferred to their linked account on hold when the
    order is paid, and released when the client approves. Otherwise an admin pays out manually.
    """
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    consultant_id = Column(Integer, ForeignKey("consultants.id", ondelete="CASCADE"), index=True, nullable=False)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    requirements = Column(Text, nullable=True)  # client brief for a service order
    amount_paise = Column(Integer, nullable=False)
    platform_fee_paise = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(String(20), nullable=False, default="pending_payment", index=True)
    # none: not paid · held: sent to the freelancer's Route account, on hold until approval ·
    # pending: approved, needs action (no payout details / Route off) · released · failed
    payout_status = Column(String(10), nullable=False, default="none")
    payout_mode = Column(String(10), nullable=True)            # route | demo | manual
    transfer_id = Column(String(40), nullable=True, index=True)  # trf_xxx
    transfer_status = Column(String(20), nullable=True)
    payout_error = Column(String(500), nullable=True)
    payout_released_at = Column(DateTime, nullable=True)
    delivery_note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    paid_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    client = relationship("Client")
    consultant = relationship("Consultant")
    service = relationship("Service")
    job = relationship("Job")
