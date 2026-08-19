# apps/api/app/models/user.py — SQLAlchemy ORM model for User entity
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    # bcrypt hash for accounts that can log in via the API (currently only the seeded admin).
    # Null for USSD-only farmers who authenticate by phone/OTP (not built yet — see security.py).
    password_hash = Column(String(255), nullable=True)
    role = Column(String(20), default="farmer", nullable=False)
    ussd_only_flag = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    owned_clinics = relationship("Clinic", back_populates="owner", foreign_keys="Clinic.owner_user_id")
    farmer_bookings = relationship("Booking", back_populates="farmer", foreign_keys="Booking.farmer_id")
    vet_bookings = relationship("Booking", back_populates="vet", foreign_keys="Booking.vet_id")
