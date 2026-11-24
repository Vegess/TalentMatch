from sqlalchemy import Column, Integer, Float, JSON, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("job_id", "consultant_id", name="uq_match_job_consultant"),)

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    consultant_id = Column(Integer, ForeignKey("consultants.id", ondelete="CASCADE"), index=True, nullable=False)
    score = Column(Float, nullable=False)
    match_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    job = relationship("Job", back_populates="matches")
    consultant = relationship("Consultant", back_populates="matches")
