# apps/api/tests/test_verification_api.py — endpoint tests for document submission/listing and the admin verify action
# Document submission is now a MULTIPART FILE UPLOAD (PART 4) and admin actions need a JWT (PART 3).

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<fake pdf for tests>>\nendobj\ntrailer\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n fake png bytes for tests"


def _doc_files(doc_type="license", contact_phone=None, filename="licence.pdf", content=PDF_BYTES, content_type="application/pdf"):
    data = {"doc_type": doc_type}
    if contact_phone is not None:
        data["contact_phone"] = contact_phone
    return data, {"file": (filename, content, content_type)}


class TestVerificationAPI:
    def test_submit_document(self, client, clinic_factory):
        clinic = clinic_factory(name="C")
        data, files = _doc_files()
        resp = client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        assert resp.status_code == 201
        body = resp.json()
        assert body["doc_type"] == "license"
        assert body["status"] == "pending"
        assert body["clinic_id"] == clinic.id
        assert body["contact_phone"] is None  # optional by default
        assert body["file_url"]  # object URL (local-disk /uploads path in tests)

    def test_submit_document_accepts_png_image(self, client, clinic_factory):
        clinic = clinic_factory(name="C")
        data, files = _doc_files(filename="id-card.png", content=PNG_BYTES, content_type="image/png")
        resp = client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        assert resp.status_code == 201
        assert resp.json()["file_url"].endswith("id-card.png")

    def test_submit_document_rejects_unsupported_type(self, client, clinic_factory):
        clinic = clinic_factory(name="C")
        data, files = _doc_files(content=b"MZ executable", content_type="application/x-msdownload", filename="virus.exe")
        resp = client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        assert resp.status_code == 415

    def test_submit_document_rejects_oversized_file(self, client, clinic_factory):
        from app.integrations.storage_client import max_upload_bytes

        clinic = clinic_factory(name="C")
        big = b"x" * (max_upload_bytes() + 1)
        data, files = _doc_files(content=big)
        resp = client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        assert resp.status_code == 413

    def test_list_documents(self, client, clinic_factory):
        clinic = clinic_factory(name="C")
        data1, files1 = _doc_files(doc_type="license")
        client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data1, files=files1)
        data2, files2 = _doc_files(doc_type="id", filename="id.pdf")
        client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data2, files=files2)
        resp = client.get(f"/api/v1/clinics/{clinic.id}/documents")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_documents_for_missing_clinic_returns_404(self, client):
        data, files = _doc_files()
        resp = client.post("/api/v1/clinics/999999/documents", data=data, files=files)
        assert resp.status_code == 404

    def test_verify_without_token_returns_401(self, client, clinic_factory):
        clinic = clinic_factory(name="C")
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "approved", "reviewed_by": "admin@vetlink254"},
        )
        assert resp.status_code == 401

    def test_verify_with_bad_jwt_returns_401(self, client, clinic_factory):
        clinic = clinic_factory(name="C")
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "approved", "reviewed_by": "admin@vetlink254"},
            headers={"Authorization": "Bearer garbage-token"},
        )
        assert resp.status_code == 401

    def test_approve_issues_unique_code(self, client, clinic_factory, admin_headers):
        clinic = clinic_factory(name="C", verifying_authority="KVB-KE", verification_status="pending_verification")
        data, files = _doc_files()
        client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "approved", "reviewed_by": "admin@vetlink254", "reason": "docs valid"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["verification_status"] == "verified"
        assert body["unique_code"].startswith("VL254-KE-")

        get_resp = client.get(f"/api/v1/clinics/{clinic.id}")
        assert get_resp.json()["verification_status"] == "verified"
        assert get_resp.json()["unique_code"] == body["unique_code"]

    def test_reject_stores_reason(self, client, clinic_factory, admin_headers):
        clinic = clinic_factory(name="C")
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "rejected", "reviewed_by": "admin@vetlink254", "reason": "License expired"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["verification_status"] == "rejected"
        assert body["reason"] == "License expired"

        get_resp = client.get(f"/api/v1/clinics/{clinic.id}")
        assert get_resp.json()["verification_note"] == "License expired"

    def test_submitting_doc_after_reject_reopens_review(self, client, clinic_factory, admin_headers):
        clinic = clinic_factory(name="C")
        client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "rejected", "reviewed_by": "admin@vetlink254"},
            headers=admin_headers,
        )
        data, files = _doc_files()
        resp = client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        assert resp.status_code == 201
        get_resp = client.get(f"/api/v1/clinics/{clinic.id}")
        assert get_resp.json()["verification_status"] == "pending_verification"


class TestVerificationSMSWiring:
    """Fire-and-forget SMS on submit + verify: farmer confirmation + board stopgap.
    SMS never breaks the flow even when it fails or the phone is blank."""

    def _patch_send(self, monkeypatch):
        from app.api.v1 import verification as ver_router

        sent = []
        monkeypatch.setattr(ver_router, "send_sms", lambda phone, msg: sent.append((phone, msg)) or True)
        return sent

    def test_submit_with_contact_phone_sms_farmer_and_board(self, client, clinic_factory, monkeypatch):
        from app.config import settings

        sent = self._patch_send(monkeypatch)
        monkeypatch.setattr(settings, "BOARD_NOTIFICATION_PHONE", "+254700000099")
        clinic = clinic_factory(name="Green Vet Clinic")
        data, files = _doc_files(contact_phone="0722123456")
        resp = client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        assert resp.status_code == 201
        assert resp.json()["contact_phone"] == "0722123456"
        # Two SMSs: farmer receipt + board notification (clinic NAME, not the farmer phone).
        assert len(sent) == 2
        farmer_phone, farmer_msg = sent[0]
        board_phone, board_msg = sent[1]
        assert farmer_phone == "0722123456"
        assert "Green Vet Clinic" in farmer_msg and "received your license document" in farmer_msg
        assert board_phone == "+254700000099"
        assert "Green Vet Clinic" in board_msg and "board/stopgap" in board_msg
        assert "0722123456" not in board_msg  # board SMS must NOT contain the farmer phone

    def test_submit_without_contact_phone_still_works_and_sms_board_only(self, client, clinic_factory, monkeypatch):
        from app.config import settings

        sent = self._patch_send(monkeypatch)
        monkeypatch.setattr(settings, "BOARD_NOTIFICATION_PHONE", "+254700000099")
        clinic = clinic_factory(name="C")
        data, files = _doc_files(doc_type="id", filename="id.pdf")
        resp = client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        assert resp.status_code == 201
        assert len(sent) == 1  # only the board notification; no farmer SMS without a phone
        assert sent[0][0] == "+254700000099"

    def test_approve_sms_decision_with_unique_code(self, client, clinic_factory, admin_headers, monkeypatch):
        from app.config import settings

        sent = self._patch_send(monkeypatch)
        monkeypatch.setattr(settings, "BOARD_NOTIFICATION_PHONE", "+254700000099")
        clinic = clinic_factory(name="C", verifying_authority="KVB-KE", verification_status="pending_verification")
        data, files = _doc_files(contact_phone="0722123456")
        client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "approved", "reviewed_by": "admin@vetlink254"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        code = resp.json()["unique_code"]
        # 2 SMS from the submit (receipt + board) + 2 from the decision (farmer + board).
        assert len(sent) == 4
        farmer_phone, farmer_msg = sent[-2]
        board_phone, board_msg = sent[-1]
        assert farmer_phone == "0722123456"
        assert "now VERIFIED" in farmer_msg and code in farmer_msg
        assert board_phone == "+254700000099" and "approved" in board_msg

    def test_reject_sms_decision_with_reason(self, client, clinic_factory, admin_headers, monkeypatch):
        from app.config import settings

        sent = self._patch_send(monkeypatch)
        monkeypatch.setattr(settings, "BOARD_NOTIFICATION_PHONE", "+254700000099")
        clinic = clinic_factory(name="C", verification_status="pending_verification")
        data, files = _doc_files(contact_phone="0722123456")
        client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "rejected", "reviewed_by": "admin@vetlink254", "reason": "License expired"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        # 2 SMS from submit + 2 from the decision.
        assert len(sent) == 4
        farmer_msg = sent[-2][1]
        assert "rejected" in farmer_msg and "License expired" in farmer_msg
        assert "approved" not in sent[-1][1]

    def test_sms_failure_never_breaks_submit(self, client, clinic_factory, monkeypatch):
        from app.api.v1 import verification as ver_router

        def boom(phone, msg):
            raise RuntimeError("SMS down")

        monkeypatch.setattr(ver_router, "send_sms", boom)
        clinic = clinic_factory(name="C")
        data, files = _doc_files(contact_phone="0722123456")
        resp = client.post(f"/api/v1/clinics/{clinic.id}/documents", data=data, files=files)
        assert resp.status_code == 201  # submission still succeeds