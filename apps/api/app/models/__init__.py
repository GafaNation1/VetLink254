# apps/api/app/models/__init__.py — Export SQLAlchemy models for database migrations and ORM operations
from app.models.user import User
from app.models.clinic import Clinic
from app.models.booking import Booking
from app.models.verification_document import VerificationDocument

__all__ = ["User", "Clinic", "Booking", "VerificationDocument"]
