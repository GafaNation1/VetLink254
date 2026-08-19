# apps/api/app/models/booking.py — SQLAlchemy ORM model for Booking entity
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    ref_code = Column(String(50), unique=True, index=True, nullable=False)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=True)
    vet_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    service_category_id = Column(Integer, nullable=True)
    animal_type = Column(String(50), nullable=False)
    status = Column(String(30), default="requested", nullable=False)
    channel = Column(String(20), default="ussd", nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    farmer = relationship("User", back_populates="farmer_bookings", foreign_keys=[farmer_id])
    vet = relationship("User", back_populates="vet_bookings", foreign_keys=[vet_id])
    clinic = relationship("Clinic", back_populates="bookings")
