# apps/api/app/schemas/kvb.py — Pydantic schema for the KVB license-verification response
from datetime import datetime
from pydantic import BaseModel


class VetVerificationResult(BaseModel):
    """Result of a live KVB license lookup. `status` reflects KVB's own record: 'active', 'expired', etc."""
    status: str
    name: str
    license_type: str
    checked_at: datetime
