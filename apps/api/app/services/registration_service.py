# apps/api/app/services/registration_service.py — Verification (KYC) business logic and unique clinic code generation
#
# IMPORTANT CONCEPTUAL DISTINCTION (per KVB leader guidance, 2026-08-15):
# This module is VetLink254's OWN INTERNAL CLINIC ONBOARDING flow — an admin approves/rejects a
# CLINIC (its docs) and it issues a VetLink254 unique_code. This is NOT KVB license verification.
# KVB (Kenya Veterinary Board) is the statutory authority on who holds a valid veterinary licence;
# VetLink254 does NOT decide or store that, and this flow does NOT change anyone's license status.
# Whether a NAMED VET has an active KVB license is a SEPARATE, NEW concept handled by the live
# verification bridge in app/integrations/kvb_client.py (exposed as GET /api/v1/verify-license),
# which calls OUT to KVB (stub today) and caches only per-session in Redis, never in Postgres.
# A clinic being "verified" on VetLink254 is deliberately different from a vet holding an active
# KVB license. The two concepts are NEVER merged into one field or one endpoint.
from sqlalchemy.orm import Session
from app.models import Clinic

def derive_region_code(verifying_authority: str | None) -> str:
    """Extract a 2-letter country/region code from a verifying authority short code.

    Convention: verifying_authority strings end with a country/region suffix, e.g.
    'KVB-KE' (Kenya), 'AVMA-US' (USA), 'EU-VET-UK' -> 'UK'. Returns 'XX' when
    nothing parseable is present so the unique_code format never breaks.
    """
    if not verifying_authority:
        return "XX"
    parts = [p for p in verifying_authority.upper().split("-") if p]
    if not parts:
        return "XX"
    suffix = parts[-1]
    return suffix if len(suffix) == 2 and suffix.isalnum() else "XX"


def generate_unique_code(db: Session, verifying_authority: str | None) -> str:
    """Generate the next sequential unique clinic code: VL254-<CC>-<sequence>.

    Format decided: VL254-<2-letter country/region code>-<zero-padded 5-digit
    sequence>, e.g. VL254-KE-00001. The region code is derived from
    `verifying_authority` (e.g. 'KVB-KE' -> 'KE'); 'XX' is used when absent.
    Sequence is the count of already-coded clinics + 1 — simple, sequential,
    and not intended to be concurrency-safe across simultaneous approvals
    (a dedicated sequence table is a future hardening step).
    """
    region = derive_region_code(verifying_authority)
    existing = db.query(Clinic).filter(Clinic.unique_code.isnot(None)).count()
    sequence = existing + 1
    return f"VL254-{region}-{sequence:05d}"


def approve_clinic(db: Session, clinic: Clinic) -> str:
    """Approve a clinic: mark verified and issue its unique code. Returns the code."""
    clinic.verification_status = "verified"
    if not clinic.unique_code:
        clinic.unique_code = generate_unique_code(db, clinic.verifying_authority)
    return clinic.unique_code


def reject_clinic(db: Session, clinic: Clinic, reason: str | None) -> None:
    """Reject a clinic: mark rejected and clear any previously issued code."""
    clinic.verification_status = "rejected"
    clinic.unique_code = None
    clinic.verification_note = reason
