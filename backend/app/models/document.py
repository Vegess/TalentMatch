from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, LargeBinary
from sqlalchemy.orm import relationship, deferred
from app.core.database import Base
from app.models._time import utcnow

OWNER_TYPES = ("job", "consultant", "service", "order")


class Document(Base):
    """A file or a URL attached to a job, freelancer profile, service or order.

    File bytes live in Postgres (document_blobs) so they survive restarts on hosts with
    ephemeral disks (Render free tier) and are deleted/backed up together with their owner.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    owner_type = Column(String(20), nullable=False, index=True)
    owner_id = Column(Integer, nullable=False, index=True)
    kind = Column(String(5), nullable=False)  # file | url
    title = Column(String(200), nullable=False)
    url = Column(String(1000), nullable=True)
    filename = Column(String(255), nullable=True)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    blob = relationship("DocumentBlob", uselist=False, cascade="all, delete-orphan", back_populates="document")


class DocumentBlob(Base):
    __tablename__ = "document_blobs"

    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    data = deferred(Column(LargeBinary, nullable=False))

    document = relationship("Document", back_populates="blob")
