# apps/ussd/tests/conftest.py — pytest fixtures for USSD adapter tests (no Redis server, no live apps/api)
# Test choices (logged in docs/progress/LOG.md):
#   - Session state: flow tests use an in-memory MemorySessionStore stand-in (no Redis needed).
#   - The real RedisSessionStore is tested directly against fakeredis (FakeRedis replaces _client).
#   - api_client.match_clinics is mocked so no live call to apps/api is made.
import copy

import pytest

import fakeredis  # noqa: F401  (import guard: must be installed with the ussd test deps)

from app.session_store import RedisSessionStore  # noqa: F401  (import guard: deps present)
from app.api_client import ApiClientError, LicenseNotFoundError  # noqa: F401


class MemorySessionStore:
    """In-memory stand-in for RedisSessionStore used by the flow tests.

    Mirrors the interface (ping/load/save/delete) with the same semantics:
    load() returns None for a missing session; save() deep-copies so later
    mutations of the caller's dict don't leak into stored state.
    """

    def __init__(self):
        self._data = {}

    def ping(self):
        return True

    def load(self, session_id):
        if not session_id:
            return None
        return copy.deepcopy(self._data.get(session_id))

    def save(self, session_id, data):
        if not session_id:
            return
        self._data[session_id] = copy.deepcopy(data)

    def delete(self, session_id):
        if not session_id:
            return
        self._data.pop(session_id, None)


class FakeApiClient:
    """Replaces app.main.api_client with canned responses; records calls and never touches HTTP.

    Supports all three delegations the adapter makes: match_clinics (find-a-vet), verify_license
    (verify-a-vet), and notify (SMS dispatch — fire-and-forget, never errors). verify_error may be a
    LicenseNotFoundError or ApiClientError instance.
    """

    def __init__(self, matches=None, error=None, verify_result=None, verify_error=None):
        self.matches = matches or []
        self.error = error
        self.verify_result = verify_result
        self.verify_error = verify_error
        self.calls = []
        self.verify_calls = []
        self.notify_calls = []

    def match_clinics(self, lat, lng, service, limit=3):
        self.calls.append({"lat": lat, "lng": lng, "service": service, "limit": limit})
        if self.error:
            raise ApiClientError(self.error)
        return self.matches

    def verify_license(self, license_number):
        self.verify_calls.append(license_number)
        if self.verify_error:
            raise self.verify_error
        if self.verify_result is None:
            raise ApiClientError("no canned verify result configured")
        return self.verify_result

    def notify(self, event, phone, context):
        self.notify_calls.append({"event": event, "phone": phone, "context": context})
        return {"event": event, "farmer_sms_sent": False, "board_sms_sent": False, "mode": "stub"}


@pytest.fixture
def flow(monkeypatch):
    """Patch app.main's session_store with an in-memory store and return it."""
    store = MemorySessionStore()
    monkeypatch.setattr("app.main.session_store", store)
    return store


@pytest.fixture
def fake_api_factory(monkeypatch):
    """Factory to patch app.main's api_client with a FakeApiClient (match + verify canned responses)."""

    def _make(matches=None, error=None, verify_result=None, verify_error=None):
        fake = FakeApiClient(
            matches=matches,
            error=error,
            verify_result=verify_result,
            verify_error=verify_error,
        )
        monkeypatch.setattr("app.main.api_client", fake)
        return fake

    return _make
