# apps/api/app/api/v1/notify.py — POST /notify: SMS dispatch on behalf of the thin USSD adapter
#
# The USSD adapter never touches SMS/Africa's Talking directly — it calls THIS endpoint over HTTP
# (thin-adapter discipline). Two events today:
#   - "match":  SMS the FARMER the clinic name / distance / unique code they just saw (written copy).
#   - "verify": SMS the FARMER their vet-verification result AND SMS the BOARD a lookup summary.
#
# The board SMS is a documented STOPGAP: the real long-term design is the board/reporting layer
# (architecture.md §3.8, listed as "not built yet" in CURRENT_STATE.md). This is a minimal SMS-based
# stand-in that gives the board visibility into verification-lookup volume until that layer exists.
# SMS is fire-and-forget: a missing SMS config (stub mode) or a send failure NEVER raises here, so it
# can never break the booking/verify flow. The endpoint is async so the (blocking, SDK-backed) sends
# run in a threadpool via send_sms_async / send_sms_async_many — the farmer + board texts on a verify
# event go out IN PARALLEL.
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.integrations.sms_client import (
    send_sms_async,
    send_sms_async_many,
    sms_client,
)

logger = logging.getLogger("app.api.v1.notify")

router = APIRouter(prefix="/notify", tags=["notify"])


class NotifyRequest(BaseModel):
    event: str  # "match" | "verify"
    phone: str = ""  # farmer phone number (recipient of the farmer SMS)
    context: Dict[str, Any] = {}  # event-specific data used to build the SMS text


class NotifyResponse(BaseModel):
    event: str
    farmer_sms_sent: bool
    board_sms_sent: bool
    mode: str  # "live" when AT creds are configured, else "stub"


def _farmer_match_message(ctx: Dict) -> str:
    return (
        f"VetLink254: {ctx.get('clinic_name', '')} is {ctx.get('distance_km')} km away. "
        f"Unique code: {ctx.get('unique_code', '')}. Service: {ctx.get('service', '')}. "
        f"Thank you for using VetLink254."
    )


def _farmer_verify_message(ctx: Dict) -> str:
    if ctx.get("status") == "active":
        return (
            f"VetLink254: {ctx.get('name', 'This vet')} is a VERIFIED KVB "
            f"{ctx.get('license_type', 'vet')}. Thank you for using VetLink254."
        )
    return (
        f"VetLink254: KVB license {ctx.get('license_number', '')} is {ctx.get('status', '')}. "
        f"This vet is NOT currently verified. Thank you for using VetLink254."
    )


def _board_verify_message(ctx: Dict, phone: str) -> str:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # No farmer personal data beyond the phone number (which is the caller-provided identifier).
    return (
        f"[VetLink254 board/stopgap] Vet-verification lookup: license "
        f"{ctx.get('license_number', '')}, at {ts}, from {phone or 'unknown phone'}."
    )


@router.post("", response_model=NotifyResponse)
async def notify(req: NotifyRequest):
    """Dispatch SMS notifications for a completed USSD step. Never raises for SMS-config reasons."""
    if req.event == "match":
        farmer_sent = await send_sms_async(req.phone, _farmer_match_message(req.context), client=sms_client)
        board_sent = False
    elif req.event == "verify":
        messages = [(req.phone, _farmer_verify_message(req.context))]
        if settings.BOARD_NOTIFICATION_PHONE:
            messages.append(
                (settings.BOARD_NOTIFICATION_PHONE, _board_verify_message(req.context, req.phone))
            )
        results = await send_sms_async_many(messages, client=sms_client)
        farmer_sent, board_sent = results[0], results[1] if len(results) > 1 else False
    else:
        raise HTTPException(status_code=422, detail=f"Unknown notify event: {req.event}")
    return NotifyResponse(
        event=req.event,
        farmer_sms_sent=farmer_sent,
        board_sms_sent=board_sent,
        mode="live" if sms_client.configured else "stub",
    )
