# apps/api/tests/test_notify_api.py — POST /api/v1/notify: SMS dispatch for the USSD adapter
# In the test env SMS is in STUB/no-op mode (AT creds unset), so the endpoint must never crash and
# must report sent=False; a fake SMSClient proves the farmer + board (verify) wiring and messages.
from app.config import settings


class FakeSMS:
    """Records sends; reports configured=True so the endpoint exercises the full dispatch path."""

    configured = True

    def __init__(self):
        self.sent = []

    def send_sms(self, phone, message):
        self.sent.append((phone, message))
        return True


class TestNotifyEndpointStub:
    def test_match_event_never_crashes_in_stub_mode(self, client):
        resp = client.post("/api/v1/notify", json={
            "event": "match",
            "phone": "+254700000001",
            "context": {"clinic_name": "PetCare", "distance_km": 2.216, "unique_code": "VL254-KE-00002", "service": "Consultation", "county": "Nairobi"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["event"] == "match"
        assert data["farmer_sms_sent"] is False  # stub mode: nothing actually sent
        assert data["board_sms_sent"] is False
        assert data["mode"] == "stub"

    def test_verify_event_never_crashes_in_stub_mode(self, client):
        resp = client.post("/api/v1/notify", json={
            "event": "verify",
            "phone": "+254700000001",
            "context": {"license_number": "KVB-1001", "name": "Dr. Wanjiku Kamau", "license_type": "Veterinary Surgeon", "status": "active"},
        })
        assert resp.status_code == 200
        assert resp.json()["farmer_sms_sent"] is False
        assert resp.json()["board_sms_sent"] is False

    def test_unknown_event_returns_422(self, client):
        resp = client.post("/api/v1/notify", json={"event": "bogus", "phone": "", "context": {}})
        assert resp.status_code == 422


class TestNotifyDispatchWithLiveClient:
    def _patch(self, monkeypatch, client_obj):
        monkeypatch.setattr("app.api.v1.notify.sms_client", client_obj)
        monkeypatch.setattr(settings, "BOARD_NOTIFICATION_PHONE", "+254700000099")

    def test_match_event_sms_contains_clinic_summary(self, client, monkeypatch):
        fake = FakeSMS()
        self._patch(monkeypatch, fake)
        resp = client.post("/api/v1/notify", json={
            "event": "match",
            "phone": "+254700000001",
            "context": {"clinic_name": "PetCare Global Clinic", "distance_km": 2.216, "unique_code": "VL254-KE-00002", "service": "Consultation", "county": "Nairobi"},
        })
        assert resp.status_code == 200
        assert resp.json()["farmer_sms_sent"] is True
        assert resp.json()["mode"] == "live"
        assert len(fake.sent) == 1  # match sends to the farmer only (no board)
        phone, msg = fake.sent[0]
        assert phone == "+254700000001"
        assert "PetCare Global Clinic" in msg
        assert "VL254-KE-00002" in msg
        assert "2.216" in msg

    def test_verify_event_sms_farmer_and_board(self, client, monkeypatch):
        fake = FakeSMS()
        self._patch(monkeypatch, fake)
        resp = client.post("/api/v1/notify", json={
            "event": "verify",
            "phone": "+254700000001",
            "context": {"license_number": "KVB-1001", "name": "Dr. Wanjiku Kamau", "license_type": "Veterinary Surgeon", "status": "active"},
        })
        assert resp.status_code == 200
        assert resp.json()["farmer_sms_sent"] is True
        assert resp.json()["board_sms_sent"] is True
        assert len(fake.sent) == 2  # farmer SMS + board SMS
        farmer_phone, farmer_msg = fake.sent[0]
        board_phone, board_msg = fake.sent[1]
        assert farmer_phone == "+254700000001"
        assert "Dr. Wanjiku Kamau" in farmer_msg and "VERIFIED KVB" in farmer_msg
        assert board_phone == "+254700000099"
        assert "board/stopgap" in board_msg and "KVB-1001" in board_msg

    def test_expired_verify_event_sms_not_verified(self, client, monkeypatch):
        fake = FakeSMS()
        self._patch(monkeypatch, fake)
        client.post("/api/v1/notify", json={
            "event": "verify",
            "phone": "+254700000001",
            "context": {"license_number": "KVB-1003", "name": "Dr. Grace Muthoni", "license_type": "Veterinary Surgeon", "status": "expired"},
        })
        assert "NOT currently verified" in fake.sent[0][1]