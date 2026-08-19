# apps/api/tests/test_verify_license_api.py — endpoint tests for GET /api/v1/verify-license
# The KVB client runs in STUB mode here (conftest sets KVB_API_BASE_URL=stub, cache disabled), so
# these tests exercise the real HTTP route against the canned stub dataset without any live KVB call.
from app.integrations.kvb_client import KVBVerificationError


class TestVerifyLicenseEndpoint:
    def test_active_license_returns_verified_result(self, client):
        resp = client.get("/api/v1/verify-license", params={"license_number": "KVB-1001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["name"] == "Dr. Wanjiku Kamau"
        assert data["license_type"] == "Veterinary Surgeon"
        assert "checked_at" in data and data["checked_at"]

    def test_expired_license_is_reported_not_active(self, client):
        resp = client.get("/api/v1/verify-license", params={"license_number": "KVB-1003"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"

    def test_unknown_license_returns_404(self, client):
        resp = client.get("/api/v1/verify-license", params={"license_number": "KVB-9999"})
        assert resp.status_code == 404
        assert "No vet found" in resp.json()["detail"]

    def test_missing_param_returns_422(self, client):
        assert client.get("/api/v1/verify-license").status_code == 422

    def test_blank_param_returns_422(self, client):
        resp = client.get("/api/v1/verify-license", params={"license_number": ""})
        assert resp.status_code == 422

    def test_kvb_failure_returns_502(self, client, monkeypatch):
        from app.api.v1 import kvb as kvb_router

        class _RaisingClient:
            def verify_license(self, license_number):
                raise KVBVerificationError("upstream down")

        monkeypatch.setattr(kvb_router, "kvb_client", _RaisingClient())
        resp = client.get("/api/v1/verify-license", params={"license_number": "KVB-1001"})
        assert resp.status_code == 502
        assert "temporarily unavailable" in resp.json()["detail"]

    def test_no_admin_token_needed(self, client):
        # Public farmer-facing lookup: works with NO X-Admin-Token header (deliberate decision, logged).
        resp = client.get("/api/v1/verify-license", params={"license_number": "KVB-1001"})
        assert resp.status_code == 200

    def test_board_notified_on_each_lookup_when_configured(self, client, monkeypatch):
        from app.config import settings
        from app.api.v1 import kvb as kvb_router

        sent = []
        monkeypatch.setattr(kvb_router, "send_sms", lambda phone, msg: sent.append((phone, msg)) or True)
        monkeypatch.setattr(settings, "BOARD_NOTIFICATION_PHONE", "+254700000099")
        # Fresh-session lookups always notify the board (task 15: board notified on each request).
        resp = client.get("/api/v1/verify-license", params={"license_number": "KVB-1001"})
        assert resp.status_code == 200
        assert len(sent) == 1
        phone, msg = sent[0]
        assert phone == "+254700000099"
        assert "KVB-1001" in msg and "board/stopgap" in msg

    def test_notify_board_param_can_be_disabled(self, client, monkeypatch):
        from app.config import settings
        from app.api.v1 import kvb as kvb_router

        sent = []
        monkeypatch.setattr(kvb_router, "send_sms", lambda phone, msg: sent.append((phone, msg)) or True)
        monkeypatch.setattr(settings, "BOARD_NOTIFICATION_PHONE", "+254700000099")
        resp = client.get("/api/v1/verify-license", params={"license_number": "KVB-1001", "notify_board": "false"})
        assert resp.status_code == 200
        assert sent == []  # explicitly disabled

    def test_no_board_sms_when_phone_unset(self, client, monkeypatch):
        from app.api.v1 import kvb as kvb_router

        sent = []
        monkeypatch.setattr(kvb_router, "send_sms", lambda phone, msg: sent.append((phone, msg)) or True)
        resp = client.get("/api/v1/verify-license", params={"license_number": "KVB-1001"})
        assert resp.status_code == 200
        assert sent == []  # BOARD_NOTIFICATION_PHONE empty in test env -> no stopgap SMS
