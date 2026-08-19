# apps/api/tests/test_match_api.py — endpoint tests for GET /api/v1/match against the test DB
import pytest


def _seed(clinic_factory):
    clinic_factory(name="PetCare Global Clinic", lat=-1.2833, lng=36.8167, services=["consultation", "vaccination"], unique_code="VL254-KE-00001")
    clinic_factory(name="Second Clinic", lat=-1.2910, lng=36.8219, services=["consultation"], unique_code="VL254-KE-00002")
    clinic_factory(name="Unverified", lat=-1.2800, lng=36.8100, services=["consultation"], verification_status="pending_verification")
    clinic_factory(name="NoCoords", lat=None, lng=None, services=["consultation"])
    clinic_factory(name="NoServices", lat=-1.2790, lng=36.8110, services=None)
    clinic_factory(name="GroomingOnly", lat=-1.2790, lng=36.8110, services=["grooming"])


class TestMatchAPI:
    def test_returns_expected_results_sorted_by_distance(self, client, clinic_factory):
        _seed(clinic_factory)
        resp = client.get("/api/v1/match/", params={"lat": -1.2921, "lng": 36.8219, "service": "consultation"})
        assert resp.status_code == 200
        data = resp.json()
        assert [d["name"] for d in data] == ["Second Clinic", "PetCare Global Clinic"]
        distances = [d["distance_km"] for d in data]
        assert distances == sorted(distances)
        assert data[0]["distance_km"] == pytest.approx(0.122, abs=0.001)

    def test_only_verified_clinics_returned(self, client, clinic_factory):
        _seed(clinic_factory)
        resp = client.get("/api/v1/match/", params={"lat": -1.2921, "lng": 36.8219, "service": "consultation"})
        names = [d["name"] for d in resp.json()]
        assert "Unverified" not in names
        assert "NoCoords" not in names
        assert "NoServices" not in names

    def test_no_matches_returns_empty_list(self, client, clinic_factory):
        _seed(clinic_factory)
        # "boarding" is offered by no clinic in the seed data -> empty list, not an error.
        resp = client.get("/api/v1/match/", params={"lat": -1.2921, "lng": 36.8219, "service": "boarding"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_limit_respected(self, client, clinic_factory):
        _seed(clinic_factory)
        resp = client.get("/api/v1/match/", params={"lat": -1.2921, "lng": 36.8219, "service": "consultation", "limit": 1})
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Second Clinic"

    def test_case_insensitive_service(self, client, clinic_factory):
        _seed(clinic_factory)
        lower = client.get("/api/v1/match/", params={"lat": -1.2921, "lng": 36.8219, "service": "consultation"}).json()
        upper = client.get("/api/v1/match/", params={"lat": -1.2921, "lng": 36.8219, "service": "CONSULTATION"}).json()
        mixed = client.get("/api/v1/match/", params={"lat": -1.2921, "lng": 36.8219, "service": "Consultation"}).json()
        assert [d["name"] for d in lower] == [d["name"] for d in upper] == [d["name"] for d in mixed]

    def test_missing_required_params_returns_422(self, client):
        assert client.get("/api/v1/match/").status_code == 422

    def test_limit_out_of_bounds_returns_422(self, client):
        params = {"lat": -1.2921, "lng": 36.8219, "service": "consultation"}
        assert client.get("/api/v1/match/", params={**params, "limit": 0}).status_code == 422
        assert client.get("/api/v1/match/", params={**params, "limit": 21}).status_code == 422
