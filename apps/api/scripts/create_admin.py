# apps/api/scripts/create_admin.py — One-off idempotent admin seeding script (env-var driven)
#
# PART 3 (minimal real auth): creates/refreshes the single admin user from ADMIN_EMAIL + ADMIN_PASSWORD.
# Run automatically by the docker-compose api start command and the Render release command (after
# `alembic upgrade head`), so a fresh deploy always has exactly one admin to log in with.
#   Usage: python -m scripts.create_admin   (from apps/api, with the app's env vars set)
#   NOTE: assumes the schema already exists (Alembic `upgrade head` runs first in both the
#   docker-compose api start command and the Render release command). No create_all here — Alembic
#   is the schema source of truth.
import sys

from app.core.database import SessionLocal
from app.core.security import ensure_admin_user

if __name__ == "__main__":
    db = SessionLocal()
    try:
        admin = ensure_admin_user(db)
    finally:
        db.close()
    if admin is None:
        print("create_admin: ADMIN_PASSWORD/ADMIN_EMAIL not set — nothing seeded (exiting 1).", file=sys.stderr)
        sys.exit(1)
    print(f"create_admin: admin OK (email={admin.email}, role={admin.role}, id={admin.id})")