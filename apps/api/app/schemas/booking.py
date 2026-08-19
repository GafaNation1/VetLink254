# apps/api/app/schemas/booking.py — Pydantic schemas for Booking request and response validation
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class BookingBase(BaseModel):
    ref_code: str
    farmer_id: int
    clinic_id: Optional[int] = None
    vet_id: Optional[int] = None
    service_category_id: Optional[int] = None
    animal_type: str
    status: str = "requested"
    channel: str = "ussd"
    scheduled_at: Optional[datetime] = None

class BookingCreate(BookingBase):
    pass

class BookingResponse(BookingBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
