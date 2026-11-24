from sqlalchemy import Column, Integer, String, Text, Float, JSON, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models._time import utcnow


class Job(Base):
    """A job description posted by a client."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(200), nullable=False, index=True)
    category = Column(String(80), nullable=True)
    description = Column(Text, nullable=False, default="")       # overview
    responsibilities = Column(Text, nullable=True)               # one per line
    requirements = Column(Text, nullable=True)                   # one per line (nice-to-haves etc.)
    required_skills = Column(JSON, nullable=False, default=list)
    min_experience_years = Column(Float, nullable=False, default=0.0)
    budget_type = Column(String(10), nullable=False, default="fixed")  # fixed | hourly
    budget_min = Column(Integer, nullable=True)  # INR
    budget_max = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False, default="INR", server_default="INR")
    location_type = Column(String(10), nullable=False, default="remote")  # remote | onsite | hybrid
    location = Column(String(120), nullable=True)
    deadline = Column(Date, nullable=True)
    status = Column(String(10), nullable=False, default="open", index=True)  # open | closed
    created_at = Column(DateTime, nullable=False, default=utcnow)

    client = relationship("Client", back_populates="jobs")
    matches = relationship("Match", back_populates="job", cascade="all, delete-orphan")
    proposals = relationship("Proposal", back_populates="job", cascade="all, delete-orphan")
