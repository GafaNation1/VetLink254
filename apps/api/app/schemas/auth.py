# apps/api/app/schemas/auth.py — Pydantic schemas for the minimal admin login (JWT)
from pydantic import BaseModel

class AuthLogin(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in_minutes: int