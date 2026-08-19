# apps/ussd/tests/test_verify_vet_flow.py — the "Verify a vet" menu branch (welcome option 2)
# Runs handle_request directly with the in-memory session store and a mocked api_client.verify_license,
# mirroring how test_ussd_flow.py covers the find-a-vet flow. No Redis, no live apps/api.
from app.api_client import ApiClientError, LicenseNotFoundError
from app.main import handle_request

ACTIVE = {
    "status": "active",
    "name": "Dr. Wanjiku Kamau",
    "license_type": "Veterinary Surgeon",
    "checked_at": "2026-08-15T10:00:00+00:00",
}
EXPIRED = {
    "status": "expired",
    "name": "Dr. Grace Muthoni",
    "license_type": "Veterinary Surgeon",
    "checked_at": "2026-08-15T10:00:00+00:00",
}


def _open_verify_prompt(sid, phone):
    """Drive a fresh English session to the verify-license (free-text) screen."""
    handle_request(sid, phone, "")
    handle_request(sid, phone, "1")      # language -> welcome
    return handle_request(sid, phone, "1*2")  # welcome -> verify a vet


class TestVerifyVetFlow:
    def test_language_then_welcome_lists_verify_a_vet(self, flow):
        sid = "+254700000011"
        body = handle_request(sid, sid, "")
        assert body.startswith("CON ")
        assert "Chagua lugha / Choose language" in body
        body = handle_request(sid, sid, "1")
        assert body.startswith("CON ")
        assert "Welcome to VetLink254" in body
        assert "1. Find a vet" in body
        assert "2. Verify a vet" in body

    def test_active_license_ends_with_verified_message_and_notifies(self, flow, fake_api_factory):
        fake = fake_api_factory(verify_result=ACTIVE)
        sid = "+254700000012"
        body = _open_verify_prompt(sid, sid)
        assert body.startswith("CON ")
        assert "KVB license number" in body

        body = handle_request(sid, sid, "1*2*KVB-1001")
        assert body.startswith("END ")
        assert "Dr. Wanjiku Kamau is a VERIFIED KVB Veterinary Surgeon" in body
        # The adapter forwarded exactly the typed number to apps/api (which calls OUT to KVB).
        assert fake.verify_calls == ["KVB-1001"]
        # After a successful lookup the adapter asked apps/api to SMS the farmer AND the board.
        assert fake.notify_calls and fake.notify_calls[-1]["event"] == "verify"
        assert fake.notify_calls[-1]["context"]["license_number"] == "KVB-1001"
        # An END screen clears the session so state cannot resurrect.
        assert flow.load(sid) is None

    def test_expired_license_ends_with_not_verified(self, flow, fake_api_factory):
        fake_api_factory(verify_result=EXPIRED)
        sid = "+254700000013"
        _open_verify_prompt(sid, sid)
        body = handle_request(sid, sid, "1*2*KVB-1003")
        assert body.startswith("END ")
        assert "NOT currently verified" in body
        assert flow.load(sid) is None

    def test_unknown_license_ends_with_not_registered(self, flow, fake_api_factory):
        fake_api_factory(verify_error=LicenseNotFoundError("no record"))
        sid = "+254700000014"
        _open_verify_prompt(sid, sid)
        body = handle_request(sid, sid, "1*2*KVB-9999")
        assert body.startswith("END ")
        assert "No vet is registered with KVB license number KVB-9999" in body
        assert flow.load(sid) is None

    def test_api_unavailable_ends_with_service_message(self, flow, fake_api_factory):
        fake_api_factory(verify_error=ApiClientError("apps/api returned HTTP 502"))
        sid = "+254700000015"
        _open_verify_prompt(sid, sid)
        body = handle_request(sid, sid, "1*2*KVB-1001")
        assert body.startswith("END ")
        assert "Service temporarily unavailable" in body
        assert flow.load(sid) is None

    def test_back_to_welcome_from_license_prompt(self, flow):
        sid = "+254700000016"
        _open_verify_prompt(sid, sid)
        body = handle_request(sid, sid, "1*2*0")
        assert body.startswith("CON ")
        assert "Welcome to VetLink254" in body
        assert flow.load(sid) is not None