# apps/api/tests/conftest.py — pytest fixtures: isolated SQLite test DB + FastAPI TestClient
# Test-DB decision (logged in docs/progress/LOG.md): a per-run file-based SQLite database in a
# temp dir, pointed at via DATABASE_URL BEFORE app modules are imported. No Postgres server needed,
# so tests run standalone without docker-compose. Behavior differences vs Postgres:
#   - SQLAlchemy JSON columns work on SQLite (stored as TEXT, transparent round-trip — verified).
#   - DateTime(timezone=True) columns come back as NAIVE datetimes on SQLite (Postgres returns
#     tz-aware); fine for response serialization in these tests.
#   - unique_code sequence is COUNT-based against THIS db, so each test starts clean (tables emptied).
import os
import tempfile

import pytest

_TEST_DB_DIR = tempfile.mkdtemp(prefix="vetlink_api_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_DIR}/test.db"
os.environ["ENVIRONMENT"] = "test"
# KVB verification bridge: force STUB mode + disable the per-session Redis cache so tests are
# deterministic and need no Redis server (see app/integrations/kvb_client.py). KVB_CACHE_TTL_SECONDS
# <= 0 disables caching; KVB_API_BASE_URL "stub" selects the temporary canned-data stub.
os.environ["KVB_API_BASE_URL"] = "stub"
os.environ["KVB_CACHE_TTL_SECONDS"] = "0"
# Minimal admin auth (PART 3): fixed test admin creds so login + protected-endpoint tests work.
os.environ["ADMIN_EMAIL"] = "admin@vetlink254.test"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
# KYC file storage (PART 4): local-disk fallback into a throwaway dir; R2 vars stay unset.
os.environ["LOCAL_UPLOAD_DIR"] = tempfile.mkdtemp(prefix="vetlink_uploads_")
os.environ["DOC_UPLOAD_MAX_MB"] = "10"

from sqlalchemy import text  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(_create_schema):
    """Empty every table before each test so tests never depend on rows left by another test."""
    db = SessionLocal()
    try:
        for table in ("verification_documents", "bookings", "clinics", "users"):
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def db_session():
    """A test-database session for service-level (non-HTTP) tests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def clinic_factory(db_session):
    """Create a Clinic row with sane defaults (verified, Nairobi, KVB-KE). Override any field via kwargs."""
    from app.models import Clinic

    def _make(**overrides):
        defaults = {
            "name": "Test Clinic",
            "county": "Nairobi",
            "verifying_authority": "KVB-KE",
            "verification_status": "verified",
            "lat": None,
            "lng": None,
            "services": None,
            "unique_code": None,
        }
        defaults.update(overrides)
        clinic = Clinic(**defaults)
        db_session.add(clinic)
        db_session.commit()
        db_session.refresh(clinic)
        return clinic

    return _make


@pytest.fixture
def client():
    """FastAPI TestClient against the test DB (startup no longer touches the schema)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_admin():
    """Ensure the env-seeded admin user exists in the test DB and return its (email, password)."""
    from app.core.database import SessionLocal as _SL
    from app.core.security import ensure_admin_user

    db = _SL()
    try:
        ensure_admin_user(db)
    finally:
        db.close()
    return "admin@vetlink254.test", "test-admin-password"


@pytest.fixture
def admin_headers(client, seeded_admin):
    """Valid admin JWT (Authorization: Bearer <token>) by logging in as the seeded admin."""
    email, password = seeded_admin
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
