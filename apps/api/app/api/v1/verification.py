# apps/api/app/api/v1/verification.py — Routers for clinic document submission, listing, and admin verify action
#
# IMPORTANT CONCEPTUAL DISTINCTION (per KVB leader guidance, 2026-08-15):
# Everything in this router is VetLink254's OWN INTERNAL CLINIC ONBOARDING — a clinic submits KYC
# documents and an admin approves/rejects the CLINIC (issuing a VetLink254 unique_code). It has
# NOTHING to do with a named vet's KVB license status. KVB is the statutory authority on licensing;
# live vet-license lookup is a SEPARATE, NEW concept served by GET /api/v1/verify-license
# (app/api/v1/kvb.py) which calls OUT to KVB (stub today). Do not confuse or merge the two.
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.integrations.sms_client import send_sms
from app.integrations.storage_client import (
    ALLOWED_DOC_TYPE_HINT,
    ALLOWED_DOC_TYPES,
    StorageError,
    max_upload_bytes,
    storage_client,
)
from app.models import Clinic, User, VerificationDocument
from app.schemas import (
    VerificationDocumentResponse,
    VerificationDecision,
    VerificationResponse,
)
from app.services.registration_service import approve_clinic, reject_clinic
from app.core.security import get_current_admin
from app.config import settings

logger = logging.getLogger("app.api.v1.verification")

router = APIRouter(prefix="/clinics", tags=["verification"])

# --- SMS message builders (fire-and-forget; see integration decision in docs/progress/LOG.md) ---
# Farmer/submitter SMSs and board stopgap SMSs. A missing/blank contact_phone or an SMS failure must
# NEVER break submission or verification, so every send is fire-and-forget and swallowed to a log.

def _submit_receipt_message(clinic_name: str, doc_type: str) -> str:
    return (
        f"VetLink254: We received your {doc_type} document for {clinic_name}. "
        f"Our team will review it and SMS you the outcome. Thank you for using VetLink254."
    )


def _board_submit_message(clinic_name: str, clinic_id: int) -> str:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # Board stopgap: clinic name/id only — deliberately NO farmer phone number in this SMS.
    return (
        f"[VetLink254 board/stopgap] KYC document submitted: clinic {clinic_name} "
        f"(id {clinic_id}), at {ts}."
    )


def _decision_message(clinic_name: str, unique_code: str, reason: str | None) -> str:
    if unique_code:
        return (
            f"VetLink254: Great news! {clinic_name} is now VERIFIED. "
            f"Your unique code is {unique_code}. Welcome to VetLink254."
        )
    return (
        f"VetLink254: {clinic_name} verification was rejected"
        + (f" ({reason})." if reason else ".")
        + " Please resubmit valid documents."
    )


def _board_decision_message(clinic_name: str, clinic_id: int, decision: str, reviewed_by: str) -> str:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return (
        f"[VetLink254 board/stopgap] Clinic {clinic_name} (id {clinic_id}) verification "
        f"{decision} by {reviewed_by}, at {ts}."
    )


def _fire_and_forget_sms(phone: str, message: str) -> None:
    """Send one SMS without ever raising. Blank/invalid phone -> skip silently (logged)."""
    if not phone or not message:
        return
    try:
        send_sms(phone, message)
    except Exception:  # never let SMS break the KYC flow
        logger.exception("BLOCKING ISSUE: fire-and-forget SMS failed for clinic KYC notification")


def _get_clinic_or_404(clinic_id: int, db: Session) -> Clinic:
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return clinic


def _latest_contact_phone(clinic_id: int, db: Session) -> str | None:
    """Return the most recently submitted document's contact_phone for this clinic, if any."""
    doc = (
        db.query(VerificationDocument)
        .filter(VerificationDocument.clinic_id == clinic_id)
        .order_by(VerificationDocument.uploaded_at.desc())
        .first()
    )
    return doc.contact_phone if doc else None


@router.post("/{clinic_id}/documents", response_model=VerificationDocumentResponse, status_code=201)
async def submit_document(
    clinic_id: int,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    contact_phone: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """Submit a verification document (multipart file upload) for a clinic, entering KYC if not already pending.

    PART 4 rework: the file is a real multipart upload (was a JSON `file_url` string). It is stored in
    Cloudflare R2 when R2 is configured, else on local disk (LOCAL_UPLOAD_DIR, served back at /uploads) so
    the local demo works with zero external credentials. The resulting object URL is saved in file_url.
    File-type/size allowlist: images (PNG/JPEG/WebP) + PDF, max DOC_UPLOAD_MAX_MB (default 10).

    SMS (fire-and-forget): the submitter (contact_phone) gets a receipt; the board gets a
    notification with the CLINIC NAME (never the farmer's phone). SMS failure never blocks this.
    """
    clinic = _get_clinic_or_404(clinic_id, db)

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{content_type or 'unknown'}'. Allowed: {ALLOWED_DOC_TYPE_HINT}.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > max_upload_bytes():
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {settings.DOC_UPLOAD_MAX_MB} MB.",
        )
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        object_url = storage_client.upload_file(file_bytes, file.filename or "document", content_type)
    except StorageError as exc:
        raise HTTPException(status_code=500, detail="Could not store the uploaded file") from exc

    doc = VerificationDocument(
        clinic_id=clinic.id,
        doc_type=doc_type,
        file_url=object_url,
        contact_phone=contact_phone,
    )
    db.add(doc)
    if clinic.verification_status not in ("pending_verification", "verified"):
        clinic.verification_status = "pending_verification"
    db.commit()
    db.refresh(doc)

    _fire_and_forget_sms(contact_phone, _submit_receipt_message(clinic.name, doc.doc_type))
    if settings.BOARD_NOTIFICATION_PHONE:
        _fire_and_forget_sms(settings.BOARD_NOTIFICATION_PHONE, _board_submit_message(clinic.name, clinic.id))
    return doc

@router.get("/{clinic_id}/documents", response_model=list[VerificationDocumentResponse])
def list_documents(clinic_id: int, db: Session = Depends(get_db)):
    """List all verification documents submitted for a clinic."""
    _get_clinic_or_404(clinic_id, db)
    return db.query(VerificationDocument).filter(VerificationDocument.clinic_id == clinic_id).all()

@router.post("/{clinic_id}/verify", response_model=VerificationResponse)
def verify_clinic(
    clinic_id: int,
    payload: VerificationDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Admin action: approve or reject a clinic's verification based on its documents.

    PART 3: protected by a real (minimal) JWT login — the caller must present a Bearer token issued
    by POST /api/v1/auth/login for the seeded admin user. Replaces the shared X-Admin-Token stopgap.
    """
    clinic = _get_clinic_or_404(clinic_id, db)
    docs = db.query(VerificationDocument).filter(
        VerificationDocument.clinic_id == clinic.id,
        VerificationDocument.status == "pending",
    ).all()
    now = datetime.now(timezone.utc)

    if payload.decision == "approved":
        unique_code = approve_clinic(db, clinic)
        for doc in docs:
            doc.status = "approved"
            doc.reviewed_by = payload.reviewed_by
            doc.reviewed_at = now
        db.commit()
        # SMS the decision to the clinic's contact (fire-and-forget) + the board stopgap.
        _fire_and_forget_sms(_latest_contact_phone(clinic.id, db), _decision_message(clinic.name, unique_code, payload.reason))
        if settings.BOARD_NOTIFICATION_PHONE:
            _fire_and_forget_sms(settings.BOARD_NOTIFICATION_PHONE, _board_decision_message(clinic.name, clinic.id, "approved", payload.reviewed_by))
        return VerificationResponse(
            message="Clinic verification approved",
            clinic_id=clinic.id,
            verification_status=clinic.verification_status,
            unique_code=unique_code,
            decision="approved",
            reason=payload.reason,
        )

    reject_clinic(db, clinic, payload.reason)
    for doc in docs:
        doc.status = "rejected"
        doc.reviewed_by = payload.reviewed_by
        doc.reviewed_at = now
    db.commit()
    _fire_and_forget_sms(_latest_contact_phone(clinic.id, db), _decision_message(clinic.name, clinic.unique_code, payload.reason))
    if settings.BOARD_NOTIFICATION_PHONE:
        _fire_and_forget_sms(settings.BOARD_NOTIFICATION_PHONE, _board_decision_message(clinic.name, clinic.id, "rejected", payload.reviewed_by))
    return VerificationResponse(
        message="Clinic verification rejected",
        clinic_id=clinic.id,
        verification_status=clinic.verification_status,
        unique_code=clinic.unique_code,
        decision="rejected",
        reason=payload.reason,
    )