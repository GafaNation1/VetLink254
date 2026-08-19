# apps/api/app/core/security.py — Minimal real auth: bcrypt password hashing + HS256 JWT + admin dependency
#
# PART 3 of the demo-readiness pass: replaces the old shared X-Admin-Token stopgap with a real
# (if minimal) login — one admin user (seeded from env vars, see ensure_admin_user / scripts/create_admin.py),
# bcrypt-hashed password, JWT issued on POST /api/v1/auth/login, required on POST /clinics/{id}/verify
# and PATCH /clinics/{id} (the same two endpoints the stopgap guarded).
#
# DELIBERATE MVP-AUTH DECISION (logged in docs/progress/LOG.md): this is NOT full production auth.
# There is a single admin role, no refresh tokens, no phone OTP, no per-farmer/clinic identity, no
# login UI, no rate limiting. It exists to remove the "anyone holding one hardcoded string can
# approve a vet" risk for the investor/partner demo. A future pilot-readiness phase must build
# roles (farmer/vet/clinic/admin), refresh tokens, phone OTP and password-reset on top of this.
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.models import User

logger = logging.getLogger("app.core.security")

ALGORITHM = "HS256"
TOKEN_TYPE = "bearer"
# Placeholder phone for the seeded admin account. The architecture makes phone the universal identity
# key on users, but a board admin is not a USSD farmer — they log in by email. This synthetic number
# is never used for SMS and is documented so it is never mistaken for a real contact.
ADMIN_PLACEHOLDER_PHONE = "+254000000000"


def hash_password(password: str) -> str:
    """bcrypt-hash a password. The hash is what gets stored in users.password_hash."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash. Never raises."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    """Issue a short-lived HS256 JWT carrying the admin user's id as `sub`."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """Decode a JWT and return the `sub` user id. Raises jwt.InvalidTokenError on bad/expired tokens."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    return int(payload["sub"])


def get_current_admin(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency guarding admin endpoints: requires a valid admin JWT (Bearer scheme).

    401 for a missing/bad/expired token (callers cannot tell which), 403 for a valid token whose
    user is not an admin. Returns the admin User row.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required (Bearer JWT)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty token")
    try:
        user_id = decode_access_token(token)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


def ensure_admin_user(db: Session) -> User | None:
    """Seed/refresh the single admin user from env vars (ADMIN_EMAIL + ADMIN_PASSWORD).

    Idempotent: creates the admin if missing, otherwise refreshes the bcrypt hash so the env var
    stays the source of truth across redeploys. Returns None (and logs) when ADMIN_PASSWORD is
    unset — the production deployment MUST set it. Dev defaults are LOCAL-DEMO placeholders only.
    """
    if not settings.ADMIN_PASSWORD:
        logger.warning(
            "ADMIN_PASSWORD unset — skipping admin seeding. Login will have no valid user until it is set."
        )
        return None
    if not settings.ADMIN_EMAIL:
        logger.warning("ADMIN_EMAIL unset — skipping admin seeding.")
        return None
    admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    password_hash = hash_password(settings.ADMIN_PASSWORD)
    if admin is None:
        admin = User(
            phone=ADMIN_PLACEHOLDER_PHONE,
            name="VetLink254 Admin",
            email=settings.ADMIN_EMAIL,
            role="admin",
            ussd_only_flag=False,
            password_hash=password_hash,
        )
        db.add(admin)
        logger.info("Seeded admin user %s (id will be assigned on commit)", settings.ADMIN_EMAIL)
    else:
        admin.password_hash = password_hash
        if admin.role != "admin":
            admin.role = "admin"
        logger.info("Refreshed admin user %s (password hash + role from env)", settings.ADMIN_EMAIL)
    db.commit()
    db.refresh(admin)
    return admin