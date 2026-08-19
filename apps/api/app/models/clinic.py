# apps/api/app/models/clinic.py — SQLAlchemy ORM model for Clinic entity
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True)
    unique_code = Column(String(50), unique=True, index=True, nullable=True)
    # `verifying_authority` is the authority that verifies THIS CLINIC for VetLink254 onboarding
    # (e.g. "KVB-KE"). It is NOT the same concept as a named vet's live KVB license status: that is
    # checked out-of-band against KVB via the bridge in app/integrations/kvb_client.py
    # (GET /api/v1/verify-license) and is never persisted here. A clinic being "verified" on
    # VetLink254 is separate from a vet holding an active KVB license.
    verifying_authority = Column(String(50), nullable=True)
    verification_note = Column(String(500), nullable=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(150), nullable=False)
    county = Column(String(100), nullable=True)
    sub_county = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    services = Column(JSON, nullable=True)
    verification_status = Column(String(30), default="pending_verification", nullable=False)
    wallet_balance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    owner = relationship("User", back_populates="owned_clinics", foreign_keys=[owner_user_id])
    bookings = relationship("Booking", back_populates="clinic")
    verification_documents = relationship("VerificationDocument", back_populates="clinic", cascade="all, delete-orphan")
