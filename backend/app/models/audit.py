from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from app.core.database import Base
from app.models._time import utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(60), nullable=False, index=True)
    target_type = Column(String(30), nullable=True)
    target_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
