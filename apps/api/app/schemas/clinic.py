# apps/api/app/schemas/clinic.py — Pydantic schemas for Clinic request and response validation
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class ClinicBase(BaseModel):
    name: str
    county: Optional[str] = None
    sub_county: Optional[str] = None
    ward: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    services: Optional[List[str]] = None
    verifying_authority: Optional[str] = None
    verification_status: str = "pending_verification"
    wallet_balance: float = 0.0

class ClinicCreate(ClinicBase):
    owner_user_id: Optional[int] = None
    unique_code: Optional[str] = None

class ClinicUpdate(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    services: Optional[List[str]] = None

class ClinicResponse(ClinicBase):
    id: int
    owner_user_id: Optional[int] = None
    unique_code: Optional[str] = None
    verification_note: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
