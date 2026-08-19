# apps/ussd/app/api_client.py — Thin HTTP client for apps/api (read-only match call); the USSD adapter never touches the database
import logging
import os

import requests

logger = logging.getLogger("ussd.api_client")


class ApiClientError(Exception):
    """Raised when apps/api cannot be reached or returns a non-success status."""


class LicenseNotFoundError(ApiClientError):
    """apps/api returned HTTP 404 for a KVB license lookup — the license is not registered with KVB.

    Deliberately distinct from ApiClientError so the adapter can show a "not verified" END screen
    instead of the generic "service unavailable" message. It is a data answer, not an outage.
    """


class ApiClient:
    """Calls apps/api's existing HTTP endpoints. No business logic lives here."""

    def __init__(self, base_url: str = "", timeout: float = 5.0):
        # Inside docker-compose the api service is reachable by its service name.
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://api:8000")).rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def match_clinics(self, lat: float, lng: float, service: str, limit: int = 3) -> list:
        """Delegate nearest-clinic matching to apps/api's GET /api/v1/match. Returns raw JSON list."""
        url = f"{self.base_url}/api/v1/match/"
        params = {"lat": lat, "lng": lng, "service": service.lower(), "limit": limit}
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.error("BLOCKING ISSUE: apps/api unreachable at %s: %s", url, exc)
            raise ApiClientError("apps/api unreachable") from exc
        if resp.status_code != 200:
            logger.error("BLOCKING ISSUE: GET %s returned HTTP %s", resp.url, resp.status_code)
            raise ApiClientError(f"apps/api returned HTTP {resp.status_code}")
        return resp.json()

    def verify_license(self, license_number: str) -> dict:
        """Delegate KVB license verification to apps/api's GET /api/v1/verify-license. Returns raw JSON dict.

        No licensing logic lives here — the adapter only forwards the number and renders the answer.
        """
        url = f"{self.base_url}/api/v1/verify-license"
        params = {"license_number": license_number}
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.error("BLOCKING ISSUE: apps/api unreachable at %s: %s", url, exc)
            raise ApiClientError("apps/api unreachable") from exc
        if resp.status_code == 404:
            raise LicenseNotFoundError(f"KVB has no record for license {license_number}")
        if resp.status_code != 200:
            logger.error("BLOCKING ISSUE: GET %s returned HTTP %s", resp.url, resp.status_code)
            raise ApiClientError(f"apps/api returned HTTP {resp.status_code}")
        return resp.json()

    def notify(self, event: str, phone: str, context: dict) -> dict:
        """Ask apps/api's POST /api/v1/notify to dispatch SMS (farmer + board stopgap) for a step.

        Thin-adapter discipline: the adapter never touches SMS / Africa's Talking directly — it only
        asks apps/api over HTTP. Fire-and-forget from the adapter's perspective: a missing SMS config
        on the API side must never break the booking/verify flow.
        """
        url = f"{self.base_url}/api/v1/notify"
        payload = {"event": event, "phone": phone, "context": context}
        try:
            resp = self._session.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.error("BLOCKING ISSUE: apps/api unreachable at %s: %s", url, exc)
            raise ApiClientError("apps/api unreachable") from exc
        if resp.status_code != 200:
            logger.error("BLOCKING ISSUE: POST %s returned HTTP %s", resp.url, resp.status_code)
            raise ApiClientError(f"apps/api returned HTTP {resp.status_code}")
        return resp.json()