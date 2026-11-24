from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow


class Service(Base):
    """A fixed-price service (gig) offered by a freelancer."""
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    consultant_id = Column(Integer, ForeignKey("consultants.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(160), nullable=False)
    category = Column(String(80), nullable=True, index=True)
    description = Column(Text, nullable=False, default="")
    deliverables = Column(Text, nullable=True)  # one per line
    price = Column(Integer, nullable=False)  # whole units of `currency`
    currency = Column(String(3), nullable=False, default="INR", server_default="INR")
    delivery_days = Column(Integer, nullable=False, default=7)
    skills = Column(JSON, nullable=False, default=list)
    status = Column(String(10), nullable=False, default="active", index=True)  # active | paused
    created_at = Column(DateTime, nullable=False, default=utcnow)

    consultant = relationship("Consultant", back_populates="services")
