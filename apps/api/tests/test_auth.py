# apps/api/tests/test_auth.py — minimal admin auth (PART 3): login, JWT issuance, protected endpoints
import jwt

from app.config import settings


class TestLogin:
    def test_login_succeeds_with_correct_credentials(self, client, seeded_admin):
        email, password = seeded_admin
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["expires_in_minutes"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES
        # The token decodes with the app's SECRET_KEY and carries the admin user id.
        payload = jwt.decode(body["access_token"], settings.SECRET_KEY, algorithms=["HS256"])
        assert "sub" in payload and "exp" in payload

    def test_login_fails_with_wrong_password(self, client, seeded_admin):
        email, _ = seeded_admin
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
        assert resp.status_code == 401

    def test_login_fails_with_unknown_email(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@vetlink254.test", "password": "whatever"},
        )
        assert resp.status_code == 401

    def test_login_fails_with_missing_fields(self, client):
        assert client.post("/api/v1/auth/login", json={"email": "a@b.c"}).status_code == 422

    def test_login_fails_for_non_admin_user(self, client):
        # A plain farmer user cannot log in through the admin endpoint even with a password_hash.
        from app.core.database import SessionLocal
        from app.core.security import hash_password
        from app.models import User

        db = SessionLocal()
        try:
            db.add(
                User(
                    phone="+254700000001",
                    name="Farmer",
                    email="farmer@vetlink254.test",
                    role="farmer",
                    password_hash=hash_password("farmer-password"),
                )
            )
            db.commit()
        finally:
            db.close()
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "farmer@vetlink254.test", "password": "farmer-password"},
        )
        assert resp.status_code == 403


class TestProtectedEndpoints:
    """Verify/PATCH now require a valid admin JWT (Bearer)."""

    def test_verify_rejects_no_token(self, client, clinic_factory):
        clinic = clinic_factory(name="C")
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "approved", "reviewed_by": "admin@vetlink254"},
        )
        assert resp.status_code == 401

    def test_verify_rejects_bad_token(self, client, clinic_factory):
        clinic = clinic_factory(name="C")
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "approved", "reviewed_by": "admin@vetlink254"},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    def test_verify_accepts_valid_jwt(self, client, clinic_factory, admin_headers):
        clinic = clinic_factory(name="C", verification_status="pending_verification")
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "approved", "reviewed_by": "admin@vetlink254"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["verification_status"] == "verified"

    def test_patch_rejects_no_token(self, client, clinic_factory):
        clinic = clinic_factory(name="C")
        resp = client.patch(f"/api/v1/clinics/{clinic.id}", json={"lat": -1.28})
        assert resp.status_code == 401

    def test_patch_accepts_valid_jwt(self, client, clinic_factory, admin_headers):
        clinic = clinic_factory(name="C")
        resp = client.patch(f"/api/v1/clinics/{clinic.id}", json={"lat": -1.28}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["lat"] == -1.28

    def test_token_for_non_admin_role_is_rejected(self, client, clinic_factory, seeded_admin):
        from app.core.security import create_access_token
        from app.models import User
        from app.core.database import SessionLocal

        clinic = clinic_factory(name="C")
        # Issue a VALID JWT for a non-admin user directly (no login route for farmers).
        db = SessionLocal()
        try:
            user = User(phone="+254700000002", name="Clinic Owner", role="clinic_owner")
            db.add(user)
            db.commit()
            db.refresh(user)
            token = create_access_token(user.id)
        finally:
            db.close()
        resp = client.post(
            f"/api/v1/clinics/{clinic.id}/verify",
            json={"decision": "approved", "reviewed_by": "owner@vetlink254.test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403