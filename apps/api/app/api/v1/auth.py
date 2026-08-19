# apps/api/app/api/v1/auth.py — Minimal admin auth: POST /api/v1/auth/login issues a JWT
#
# PART 3 of the demo-readiness pass. Deliberate MVP scope (logged in docs/progress/LOG.md): ONE admin
# user, bcrypt password, HS256 JWT, no refresh tokens / roles / OTP / rate limiting. Login only
# succeeds for the seeded admin (role == "admin"); a plain farmer user cannot log in here.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas import AuthLogin, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: AuthLogin, db: Session = Depends(get_db)):
    """Exchange admin email + password for a short-lived Bearer JWT."""
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin accounts can log in here")
    return TokenResponse(
        access_token=create_access_token(user.id),
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )