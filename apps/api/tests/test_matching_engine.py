# apps/api/tests/test_matching_engine.py — tests for haversine_km (pure math) and find_nearest_clinics (filters/sort/limit)
import pytest

from app.services.matching_engine import find_nearest_clinics, haversine_km


class TestHaversineKm:
    """Independent distance values: 1 degree of latitude == ~111.195 km; the London<->Paris
    great-circle distance is a well-known ~343.5 km; the Nairobi fixture comes from the
    live-verified docs (downtown Nairobi -> PetCare Global Clinic ~1.137 km)."""

    def test_equator_one_degree_of_latitude(self):
        assert haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.195, rel=1e-3)

    def test_nairobi_reference_fixture(self):
        assert haversine_km(-1.2921, 36.8219, -1.2833, 36.8167) == pytest.approx(1.1365, abs=1e-3)

    def test_london_to_paris(self):
        assert haversine_km(51.5074, -0.1278, 48.8566, 2.3522) == pytest.approx(343.56, rel=1e-2)

    def test_zero_distance_for_identical_points(self):
        assert haversine_km(-1.2833, 36.8167, -1.2833, 36.8167) == pytest.approx(0.0, abs=1e-9)

    def test_symmetry(self):
        forward = haversine_km(-1.2921, 36.8219, -1.2833, 36.8167)
        reverse = haversine_km(-1.2833, 36.8167, -1.2921, 36.8219)
        assert forward == pytest.approx(reverse, rel=1e-9)


class TestFindNearestClinics:
    """Uses a real SQLite test session so the DB-level verification_status filter is exercised too.
    Query point for most tests: downtown Nairobi (-1.2921, 36.8219)."""

    def test_only_verified_clinics_returned(self, db_session, clinic_factory):
        clinic_factory(name="Verified", lat=-1.2833, lng=36.8167, services=["consultation"], verification_status="verified")
        clinic_factory(name="Pending", lat=-1.2833, lng=36.8167, services=["consultation"], verification_status="pending_verification")
        clinic_factory(name="Rejected", lat=-1.2833, lng=36.8167, services=["consultation"], verification_status="rejected")
        names = [c.name for c in find_nearest_clinics(db_session, -1.2921, 36.8219, "consultation")]
        assert names == ["Verified"]

    def test_case_insensitive_service_match(self, db_session, clinic_factory):
        clinic_factory(name="A", lat=-1.2833, lng=36.8167, services=["CONSULTATION", "Vaccination"])
        for svc in ("consultation", "CONSULTATION", "Consultation"):
            assert [c.name for c in find_nearest_clinics(db_session, -1.2921, 36.8219, svc)] == ["A"]

    def test_null_or_empty_services_excluded(self, db_session, clinic_factory):
        clinic_factory(name="Null", lat=-1.2833, lng=36.8167, services=None)
        clinic_factory(name="Empty", lat=-1.2833, lng=36.8167, services=[])
        assert find_nearest_clinics(db_session, -1.2921, 36.8219, "consultation") == []

    def test_missing_latlng_excluded(self, db_session, clinic_factory):
        clinic_factory(name="NoCoord", lat=None, lng=None, services=["consultation"])
        clinic_factory(name="PartialCoord", lat=-1.2833, lng=None, services=["consultation"])
        assert find_nearest_clinics(db_session, -1.2921, 36.8219, "consultation") == []

    def test_results_sorted_by_distance_ascending(self, db_session, clinic_factory):
        clinic_factory(name="Far", lat=-1.2833, lng=36.8167, services=["consultation"])
        clinic_factory(name="Near", lat=-1.2910, lng=36.8219, services=["consultation"])
        clinic_factory(name="Mid", lat=-1.2900, lng=36.8200, services=["consultation"])
        names = [c.name for c in find_nearest_clinics(db_session, -1.2921, 36.8219, "consultation")]
        assert names == ["Near", "Mid", "Far"]

    def test_limit_respected(self, db_session, clinic_factory):
        clinic_factory(name="Near", lat=-1.2910, lng=36.8219, services=["consultation"])
        clinic_factory(name="Mid", lat=-1.2900, lng=36.8200, services=["consultation"])
        clinic_factory(name="Far", lat=-1.2833, lng=36.8167, services=["consultation"])
        assert len(find_nearest_clinics(db_session, -1.2921, 36.8219, "consultation", limit=2)) == 2
        assert [c.name for c in find_nearest_clinics(db_session, -1.2921, 36.8219, "consultation", limit=1)] == ["Near"]

    def test_no_matches_returns_empty_list(self, db_session, clinic_factory):
        clinic_factory(name="GroomingOnly", lat=-1.2833, lng=36.8167, services=["grooming"])
        assert find_nearest_clinics(db_session, -1.2921, 36.8219, "consultation") == []
