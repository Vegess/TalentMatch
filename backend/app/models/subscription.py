from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    plan_type = Column(String(20), nullable=False)  # FREE | PREMIUM | ENTERPRISE
    status = Column(String(20), nullable=False, default="active")  # active | expired | cancelled
    start_date = Column(DateTime, nullable=False, default=utcnow)
    end_date = Column(DateTime, nullable=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)

    client = relationship("Client", back_populates="subscriptions")

    def is_active(self) -> bool:
        if self.status != "active":
            return False
        return self.end_date is None or self.end_date > utcnow()
