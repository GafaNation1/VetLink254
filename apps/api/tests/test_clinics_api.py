# apps/api/tests/test_clinics_api.py — endpoint tests for GET/POST/PATCH /api/v1/clinics via TestClient
class TestClinicsAPI:
    def test_create_clinic(self, client):
        resp = client.post(
            "/api/v1/clinics/",
            json={"name": "New Clinic", "county": "Nairobi", "verifying_authority": "KVB-KE"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Clinic"
        assert data["verification_status"] == "pending_verification"
        assert "id" in data

    def test_list_clinics(self, client, clinic_factory):
        clinic_factory(name="One")
        clinic_factory(name="Two")
        resp = client.get("/api/v1/clinics/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_one_clinic(self, client, clinic_factory):
        clinic = clinic_factory(name="One")
        resp = client.get(f"/api/v1/clinics/{clinic.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "One"

    def test_get_missing_clinic_returns_404(self, client):
        resp = client.get("/api/v1/clinics/999999")
        assert resp.status_code == 404

    def test_patch_without_token_returns_401(self, client, clinic_factory):
        clinic = clinic_factory(name="One")
        resp = client.patch(f"/api/v1/clinics/{clinic.id}", json={"lat": -1.2833})
        assert resp.status_code == 401

    def test_patch_with_bad_token_returns_401(self, client, clinic_factory):
        clinic = clinic_factory(name="One")
        resp = client.patch(
            f"/api/v1/clinics/{clinic.id}",
            json={"lat": -1.2833},
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code == 401

    def test_patch_with_valid_jwt_updates(self, client, clinic_factory, admin_headers):
        clinic = clinic_factory(name="One")
        resp = client.patch(
            f"/api/v1/clinics/{clinic.id}",
            json={"lat": -1.2833, "lng": 36.8167, "services": ["consultation"]},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["lat"] == -1.2833
        assert data["lng"] == 36.8167
        assert data["services"] == ["consultation"]

    def test_patch_missing_clinic_returns_404_with_jwt(self, client, admin_headers):
        resp = client.patch("/api/v1/clinics/999999", json={"lat": -1.28}, headers=admin_headers)
        assert resp.status_code == 404