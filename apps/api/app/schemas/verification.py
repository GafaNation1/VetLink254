# apps/api/app/schemas/verification.py — Pydantic schemas for verification documents and admin decisions
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict

# NOTE: VerificationDocumentCreate was REMOVED in the PART 4 file-upload rework — document submission
# now takes a multipart `file` (UploadFile) + `doc_type`/`contact_phone` form fields instead of a
# JSON `file_url` string (see app/api/v1/verification.py). The uploaded object's URL is stored in the
# existing file_url column.

class VerificationDocumentResponse(BaseModel):
    id: int
    clinic_id: int
    doc_type: str
    file_url: str
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    uploaded_at: datetime
    contact_phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class VerificationDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewed_by: str
    reason: Optional[str] = None

class VerificationResponse(BaseModel):
    message: str
    clinic_id: int
    verification_status: str
    unique_code: Optional[str] = None
    decision: str
    reason: Optional[str] = None