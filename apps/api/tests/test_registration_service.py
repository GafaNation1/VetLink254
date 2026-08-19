# apps/api/tests/test_registration_service.py — tests for unique-code generation and approve/reject logic
from app.services.registration_service import (
    approve_clinic,
    derive_region_code,
    generate_unique_code,
    reject_clinic,
)


class TestDeriveRegionCode:
    def test_kvb_ke(self):
        assert derive_region_code("KVB-KE") == "KE"

    def test_avma_us(self):
        assert derive_region_code("AVMA-US") == "US"

    def test_multi_segment(self):
        assert derive_region_code("EU-VET-UK") == "UK"

    def test_lowercase_is_normalized(self):
        assert derive_region_code("kvb-ke") == "KE"

    def test_missing_authority_falls_back_to_xx(self):
        assert derive_region_code(None) == "XX"
        assert derive_region_code("") == "XX"

    def test_unparseable_falls_back_to_xx(self):
        assert derive_region_code("KVB") == "XX"
        assert derive_region_code("KVB-KENYA") == "XX"
        assert derive_region_code("KVB--") == "XX"

    def test_trailing_dash_still_parses_region(self):
        # "KVB-KE-" -> empty trailing part is filtered, so the region is still KE.
        assert derive_region_code("KVB-KE-") == "KE"


class TestGenerateUniqueCode:
    def test_format_is_vl254_region_5digit_seq(self, db_session):
        code = generate_unique_code(db_session, "KVB-KE")
        assert code == "VL254-KE-00001"

    def test_sequence_increments_global_count(self, db_session, clinic_factory):
        clinic_factory(name="A", unique_code="VL254-KE-00001", verifying_authority="KVB-KE")
        clinic_factory(name="B", unique_code="VL254-KE-00002", verifying_authority="KVB-KE")
        assert generate_unique_code(db_session, "AVMA-US") == "VL254-US-00003"

    def test_region_from_authority(self, db_session):
        assert generate_unique_code(db_session, "AVMA-US") == "VL254-US-00001"
        assert generate_unique_code(db_session, "EU-VET-UK") == "VL254-UK-00001"

    def test_missing_authority_uses_xx(self, db_session):
        assert generate_unique_code(db_session, None) == "VL254-XX-00001"

    def test_zero_padded_five_digits(self, db_session):
        code = generate_unique_code(db_session, "KVB-KE")
        seq = code.rsplit("-", 1)[1]
        assert len(seq) == 5
        assert seq == "00001"


class TestApproveReject:
    def test_approve_sets_verified_and_issues_code(self, db_session, clinic_factory):
        clinic = clinic_factory(name="C", verifying_authority="KVB-KE", verification_status="pending_verification")
        code = approve_clinic(db_session, clinic)
        assert clinic.verification_status == "verified"
        assert clinic.unique_code == "VL254-KE-00001"
        assert code == clinic.unique_code

    def test_approve_keeps_existing_code(self, db_session, clinic_factory):
        clinic = clinic_factory(name="C", unique_code="VL254-KE-00001")
        approve_clinic(db_session, clinic)
        assert clinic.unique_code == "VL254-KE-00001"

    def test_reject_sets_rejected_and_stores_reason(self, db_session, clinic_factory):
        clinic = clinic_factory(name="C", unique_code="VL254-KE-00001")
        reject_clinic(db_session, clinic, "License expired")
        assert clinic.verification_status == "rejected"
        assert clinic.unique_code is None
        assert clinic.verification_note == "License expired"
