# apps/api/app/models/verification_document.py — SQLAlchemy ORM model for clinic/vet KYC verification documents
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class VerificationDocument(Base):
    __tablename__ = "verification_documents"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    doc_type = Column(String(50), nullable=False)
    file_url = Column(String(500), nullable=False)
    # Optional Kenyan phone of the farmer/submitter, used for confirmation + decision SMS.
    contact_phone = Column(String(20), nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    clinic = relationship("Clinic", back_populates="verification_documents")
