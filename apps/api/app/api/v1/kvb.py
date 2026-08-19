# apps/api/app/api/v1/kvb.py — Router for GET /verify-license, the live KVB license-lookup bridge
#
# AUTH DECISION (logged): this endpoint is deliberately PUBLIC — a farmer-facing read-only lookup
# (a farmer can check a vet's license before trusting them), so it does NOT use the admin
# X-Admin-Token stopgap. It is a read-only data lookup against KVB (stub today); any paid service
# or levy is future scope and would not make this lookup private.
#
# CONCEPT DISTINCTION: this is NOT the internal clinic-onboarding verification (app/api/v1/verification.py).
# This checks a NAMED VET's live license status with KVB (the licensing authority). VetLink254 is not
# the source of truth and never stores this status — only caches it per-session in Redis.
#
# BOARD NOTIFICATION (task 15): each time this endpoint is hit, the board is notified via SMS
# (fire-and-forget, controlled by the `notify_board` parameter, default on, gated by the
# BOARD_NOTIFICATION_PHONE setting). REDUNDANCY NOTE (logged in docs/progress/LOG.md): the USSD
# adapter also asks apps/api's /notify ("verify" event) to SMS the board after a completed flow, so
# the board can receive two texts per verification — one at lookup time here, one at flow end. Both
# are documented stopgaps until the real board/reporting layer exists.
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.integrations.kvb_client import (
    KVBNotFoundError,
    KVBVerificationClient,
    KVBVerificationError,
)
from app.integrations.sms_client import send_sms
from app.schemas import VetVerificationResult

logger = logging.getLogger("app.api.v1.kvb")

router = APIRouter(prefix="/verify-license", tags=["kvb"])

# One client for the whole process. STUB MODE by default (canned data + WARNING log per call);
# point KVB_API_BASE_URL at the real KVB API with real OAuth2 credentials to go live — a drop-in
# replacement, no other code changes needed if the interface is respected.
kvb_client = KVBVerificationClient()


def _notify_board(license_number: str) -> None:
    """Fire-and-forget board SMS on a lookup. Never raises, never blocks the response."""
    if not settings.BOARD_NOTIFICATION_PHONE:
        return
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        send_sms(
            settings.BOARD_NOTIFICATION_PHONE,
            f"[VetLink254 board/stopgap] License lookup: {license_number}, at {ts}.",
        )
    except Exception:  # SMS must never break the lookup response
        logger.exception("BLOCKING ISSUE: board SMS failed for license lookup %s", license_number)


@router.get("", response_model=VetVerificationResult)
def verify_license(
    license_number: str = Query(..., min_length=1, description="KVB licence number to check live against KVB"),
    notify_board: bool = Query(True, description="SMS the board a notification for this lookup (stopgap)"),
):
    """Look up a vet's KVB license status — always checked live against KVB, never stored in Postgres.

    status "active" => the vet is currently licensed; any other status (e.g. "expired") => not.
    Unknown license numbers return 404; KVB/API failures return 502.
    """
    if notify_board:
        _notify_board(license_number)
    try:
        result = kvb_client.verify_license(license_number)
    except KVBNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KVBVerificationError as exc:
        logger.error("KVB license verification failed for %s: %s", license_number, exc)
        raise HTTPException(
            status_code=502,
            detail="KVB verification service temporarily unavailable",
        ) from exc
    return VetVerificationResult(
        status=result["status"],
        name=result["name"],
        license_type=result["license_type"],
        checked_at=datetime.now(timezone.utc),
    )
