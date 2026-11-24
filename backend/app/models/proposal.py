from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow


class Proposal(Base):
    """A freelancer's application to a job."""
    __tablename__ = "proposals"
    __table_args__ = (UniqueConstraint("job_id", "consultant_id", name="uq_proposal_job_consultant"),)

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    consultant_id = Column(Integer, ForeignKey("consultants.id", ondelete="CASCADE"), index=True, nullable=False)
    cover_letter = Column(Text, nullable=False)
    bid_amount = Column(Integer, nullable=False)  # INR
    estimated_days = Column(Integer, nullable=True)
    status = Column(String(15), nullable=False, default="submitted")  # submitted|shortlisted|accepted|rejected|withdrawn
    created_at = Column(DateTime, nullable=False, default=utcnow)

    job = relationship("Job", back_populates="proposals")
    consultant = relationship("Consultant", back_populates="proposals")
