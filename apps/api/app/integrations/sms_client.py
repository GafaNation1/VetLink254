# apps/api/app/integrations/sms_client.py — Africa's Talking SMS via the OFFICIAL python SDK (send_sms -> bool)
#
# DECISION (logged in docs/progress/LOG.md): we use the official `africastalking` SDK (pinned to
# 2.0.3) instead of hand-rolled httpx against the REST endpoint. Consequences:
#   - The SDK HARDCODES its base URL and auto-routes to https://api.sandbox.africastalking.com when
#     the username is exactly "sandbox" — so AT_SMS_BASE_URL is now DEAD CONFIG and has been removed
#     from config.py / .env.example / docker-compose.yml / this module.
#   - The SDK validates phone numbers against ^\+\d{1,3}\d{3,}$ and raises ValueError on a bad one,
#     so EVERY caller routes through format_kenyan_phone() first (which guarantees "+254...").
#   - The SDK raises AfricasTalkingException on any non-2xx response; we catch it here.
#
# When AT_USERNAME or AT_API_KEY is unset (the dev default) the client runs in STUB/no-op mode: it
# logs a WARNING and returns False WITHOUT sending — a missing SMS config must NEVER break the
# booking/verify flow (same pattern as the kvb_client stub). `sdk` is injectable for tests so no
# network call is ever made from the test suite.
import asyncio
import logging
import re

from app.config import settings

try:  # africastalking is a hard runtime dep (pinned in requirements.txt)
    import africastalking
except ImportError:  # pragma: no cover - only hit if deps weren't installed
    africastalking = None

logger = logging.getLogger("app.integrations.sms_client")


def format_kenyan_phone(number):
    """Normalize a Kenyan phone number to the +2547XXXXXXXX form the AT SDK requires.

    Accepts "07XXXXXXXX", "7XXXXXXXX", "2547XXXXXXXX", "+2547XXXXXXXX" (with/without spaces and
    dashes). Returns None for blank or non-Kenyan numbers so callers can skip the SMS safely.
    """
    if not number:
        return None
    digits = re.sub(r"\D", "", str(number))
    if len(digits) == 9 and digits.startswith("7"):  # 7XXXXXXXX
        digits = "254" + digits
    elif len(digits) == 10 and digits.startswith("0"):  # 07XXXXXXXX
        digits = "254" + digits[1:]
    elif len(digits) == 12 and digits.startswith("254"):  # 2547XXXXXXXX / +2547XXXXXXXX
        pass
    else:
        return None
    return "+" + digits


def _masked(phone_number):
    """Mask a phone number for logs, showing only the last 4 digits (e.g. +2547****5678)."""
    if not phone_number:
        return "unknown"
    text = str(phone_number)
    if len(text) < 8:
        return "****"
    return text[:-8] + "****" + text[-4:]


def _safe_recipient(phone_number):
    """Phone number safe to put in logs: masked version, or the literal "unknown" when blank."""
    if not phone_number:
        return "unknown"
    return _masked(phone_number)


class SMSClient:
    """Africa's Talking SMS client backed by the official SDK, with a single public method:
    send_sms(phone_number, message) -> bool (never raises)."""

    def __init__(self, username=None, api_key=None, sender_id=None, sdk=None):
        self.username = username if username is not None else settings.AT_USERNAME
        self.api_key = api_key if api_key is not None else settings.AT_API_KEY
        self.sender_id = sender_id if sender_id is not None else settings.AT_SENDER_ID
        self.configured = bool(self.username and self.api_key)
        self._sdk = sdk if sdk is not None else africastalking
        self._sms = None
        if self.configured:
            if self._sdk is None:
                self.configured = False
                logger.error("BLOCKING ISSUE: africastalking SDK not installed but AT creds are set")
            else:
                try:
                    self._sdk.initialize(self.username, self.api_key)
                    self._sms = self._sdk.SMS
                except Exception:
                    logger.error("BLOCKING ISSUE: africastalking.initialize failed", exc_info=True)
                    self.configured = False
                    self._sms = None

    def send_sms(self, phone_number, message):
        """Send one SMS. Returns True on success, False on any failure (never raises).

        Stub mode (AT creds unset) logs a WARNING and skips — this is the dev default, so the whole
        booking/verify flow works with zero SMS infrastructure. The SDK only accepts +254-formatted
        numbers, so the phone is normalized via format_kenyan_phone() before the call.
        """
        if not phone_number or not message:
            return False
        recipient = format_kenyan_phone(phone_number)
        if not recipient:
            logger.warning(
                "SMSClient: skipping SMS to non-Kenyan/invalid phone %s (message: %.60s...)",
                _safe_recipient(phone_number),
                message,
            )
            return False
        if not self.configured or self._sms is None:
            logger.warning(
                "SMSClient in STUB/no-op mode — AT_USERNAME/AT_API_KEY unset, NOT sending SMS to %s. "
                "Set AT_USERNAME + AT_API_KEY (+ optionally AT_SENDER_ID) for real SMS. "
                "Use username='sandbox' to route to the AT sandbox automatically.",
                _safe_recipient(recipient),
            )
            return False
        try:
            self._sms.send(
                message,
                [recipient],
                sender_id=self.sender_id or None,
            )
            logger.info("SMS sent to %s (%.60s...)", _safe_recipient(recipient), message)
            return True
        except Exception as exc:
            logger.error("BLOCKING ISSUE: Africa's Talking SMS send failed for %s: %s",
                         _safe_recipient(recipient), exc)
            return False


# One shared client for the whole process (notify, verification, kvb routers all use it).
sms_client = SMSClient()


def send_sms(phone_number, message, client=None):
    """Module-level sync helper: send one SMS, returning True/False. Never raises."""
    return (client or sms_client).send_sms(phone_number, message)


async def send_sms_async(phone_number, message, client=None):
    """Module-level async helper: run the (blocking) SDK send in a threadpool so the event loop is
    never blocked. SMS is fire-and-forget: returns True/False and never raises."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, send_sms, phone_number, message, client)


async def send_sms_async_many(messages, client=None):
    """Send several SMSs in parallel (threadpool), e.g. the farmer + board texts at once.

    messages: iterable of (phone_number, message). Returns a list of bools, one per send, in order.
    """
    loop = asyncio.get_running_loop()
    sends = [loop.run_in_executor(None, send_sms, phone, msg, client) for phone, msg in messages]
    return await asyncio.gather(*sends)
