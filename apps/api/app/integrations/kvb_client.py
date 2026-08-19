# apps/api/app/integrations/kvb_client.py — KVB (Kenya Veterinary Board) license-verification client
#
# VetLink254 is NOT the authority on who holds a valid veterinary licence — KVB is. VetLink254 is a
# B2C bridge: it lets a farmer check a vet's license status and get matched to one, by calling OUT to
# KVB's own practitioner-management system (MMS, mms.kenyavetboard.or.ke) once KVB exposes an API.
#
# STUB MODE (TEMPORARY): KVB does not yet expose a public API, so this client ships in STUB MODE by
# default (KVB_API_BASE_URL unset or "stub"): it returns canned responses from an in-memory dict of a
# few fake license numbers and logs a WARNING on EVERY stub call so it can never be mistaken for a
# real integration. Swapping in the real endpoint is a drop-in change: set KVB_API_BASE_URL to the
# real URL and supply real KVB_CLIENT_ID/KVB_CLIENT_SECRET (OAuth2 client-credentials). No other code
# should need to change if the interface is respected.
#
# CACHING: successful lookups are cached in Redis for a short TTL (default 180s) matching the USSD
# session TTL — license status must ALWAYS be checked live per session. Results are never persisted
# to Postgres. If Redis is unreachable the client degrades to an uncached call with a WARNING.
import json
import logging
import os
from typing import Optional

import httpx
import redis

from app.config import settings

logger = logging.getLogger("app.integrations.kvb_client")

# Deliberately matches the USSD session TTL (apps/ussd/app/session_store.py, 180s) so a cached
# license status can never outlive the session it was fetched in — every new session re-checks live.
# <= 0 disables caching entirely.
KVB_CACHE_TTL_SECONDS = int(os.getenv("KVB_CACHE_TTL_SECONDS", "180"))

# Values that select stub mode: unset (default) or the literal "stub".
STUB_MODE_MARKERS = ("", "stub")


class KVBVerificationError(Exception):
    """KVB license verification failed for a transport/auth/data reason (not a not-found)."""


class KVBNotFoundError(KVBVerificationError):
    """KVB has no record for this license number (HTTP 404 equivalent)."""


# TEMPORARY stub dataset — EXISTS ONLY so the rest of the system can be built and tested against a
# realistic interface today. MUST be replaced with a real HTTP call to KVB's API once KVB exposes
# one. Every stub use logs a WARNING (see _stub_fetch); never let the stub look like a real integration.
_STUB_LICENSES = {
    "KVB-1001": {"status": "active", "name": "Dr. Wanjiku Kamau", "license_type": "Veterinary Surgeon"},
    "KVB-1002": {"status": "active", "name": "Dr. Brian Otieno", "license_type": "Veterinary Surgeon"},
    "KVB-1003": {"status": "expired", "name": "Dr. Grace Muthoni", "license_type": "Veterinary Surgeon"},
}


def _cache_key(license_number: str) -> str:
    return f"kvb:license:{license_number}"


class KVBVerificationClient:
    """Client for KVB's license-verification API.

    ONE public method: verify_license(license_number) -> dict{status, name, license_type}.
    Raises KVBNotFoundError when KVB has no record, KVBVerificationError on any other failure.
    Real mode calls OUT to KVB via OAuth2 client-credentials (endpoint shapes below are the
    documented contract to build against and must be confirmed against KVB's real API). Stub mode
    (default) returns canned data and logs a WARNING. Successful results are cached in Redis
    (per-session TTL, never Postgres).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        timeout: float = 5.0,
        cache_ttl: Optional[int] = None,
        redis_client: Optional["redis.Redis"] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        # Defaults come from settings/env. KVB_API_BASE_URL unset or "stub" => stub mode.
        self.base_url = (base_url if base_url is not None else settings.KVB_API_BASE_URL or "stub").strip().rstrip("/")
        self.client_id = client_id if client_id is not None else settings.KVB_CLIENT_ID
        self.client_secret = client_secret if client_secret is not None else settings.KVB_CLIENT_SECRET
        self.timeout = timeout
        self.cache_ttl = int(cache_ttl if cache_ttl is not None else settings.KVB_CACHE_TTL_SECONDS)
        # redis_client is injectable for tests; otherwise created lazily from settings.REDIS_URL.
        self._redis = redis_client
        self._transport = transport  # injectable httpx.MockTransport for tests
        self._is_stub = self.base_url.lower() in STUB_MODE_MARKERS

    # -- Public interface -----------------------------------------------------

    def verify_license(self, license_number: str) -> dict:
        """Return {status, name, license_type} for a KVB license number, or raise KVBVerificationError."""
        if not license_number or not str(license_number).strip():
            raise KVBVerificationError("license_number is required")
        license_number = str(license_number).strip()
        key = _cache_key(license_number)
        if self.cache_ttl > 0:
            cached = self._cache_get(key)
            if cached is not None:
                logger.info("Serving KVB license %s from the per-session Redis cache (TTL %ss)", license_number, self.cache_ttl)
                return cached
        result = self._fetch(license_number)
        # Only cache successful (found) results; not-found/errors raise and are never cached.
        if self.cache_ttl > 0:
            self._cache_set(key, result)
        return result

    # -- Fetch path (stub vs real HTTP) ---------------------------------------

    def _fetch(self, license_number: str) -> dict:
        if self._is_stub:
            return self._stub_fetch(license_number)
        return self._http_fetch(license_number)

    def _stub_fetch(self, license_number: str) -> dict:
        logger.warning(
            "KVBVerificationClient in TEMPORARY STUB MODE — returning canned data for license %s. "
            "This is NOT a real KVB integration. Set KVB_API_BASE_URL to the real KVB API endpoint "
            "once KVB exposes one.", license_number,
        )
        entry = _STUB_LICENSES.get(license_number)
        if entry is None:
            raise KVBNotFoundError(f"No vet found with KVB license number {license_number}")
        return dict(entry)

    def _http_fetch(self, license_number: str) -> dict:
        token = self._fetch_access_token()
        # Assumed KVB endpoint shape (documented contract): GET {base}/api/v1/verify/{license_number}
        # returning {"status": "active", "name": "...", "license_type": "..."}. Confirm against KVB's
        # real API when it exists; the interface stays the same.
        url = f"{self.base_url}/api/v1/verify/{license_number}"
        try:
            with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
                resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
        except httpx.RequestError as exc:
            logger.error("BLOCKING ISSUE: KVB API unreachable at %s: %s", url, exc)
            raise KVBVerificationError("KVB API unreachable") from exc
        if resp.status_code == 404:
            raise KVBNotFoundError(f"No vet found with KVB license number {license_number}")
        if resp.status_code != 200:
            logger.error("BLOCKING ISSUE: GET %s returned HTTP %s", url, resp.status_code)
            raise KVBVerificationError(f"KVB API returned HTTP {resp.status_code}")
        data = resp.json()
        for key in ("status", "name", "license_type"):
            if key not in data:
                raise KVBVerificationError(f"KVB API response missing '{key}'")
        return data

    def _fetch_access_token(self) -> str:
        # Assumed KVB token endpoint (documented contract): POST {base}/oauth/token with OAuth2
        # client-credentials grant. Confirm against KVB's real API when it exists.
        url = f"{self.base_url}/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
                resp = client.post(url, data=payload)
        except httpx.RequestError as exc:
            logger.error("BLOCKING ISSUE: KVB token endpoint unreachable at %s: %s", url, exc)
            raise KVBVerificationError("KVB token endpoint unreachable") from exc
        if resp.status_code != 200:
            logger.error("BLOCKING ISSUE: POST %s returned HTTP %s", url, resp.status_code)
            raise KVBVerificationError(f"KVB token endpoint returned HTTP {resp.status_code}")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise KVBVerificationError("KVB token response missing access_token")
        return token

    # -- Per-session Redis cache (never persisted to Postgres) ------------------

    def _get_redis(self) -> "redis.Redis":
        if self._redis is None:
            self._redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    def _cache_get(self, key: str) -> Optional[dict]:
        try:
            raw = self._get_redis().get(key)
        except redis.RedisError as exc:
            logger.warning("Redis cache read failed for KVB verification (continuing without cache): %s", exc)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def _cache_set(self, key: str, result: dict) -> None:
        try:
            self._get_redis().setex(key, self.cache_ttl, json.dumps(result))
        except redis.RedisError as exc:
            logger.warning("Redis cache write failed for KVB verification (continuing without cache): %s", exc)
