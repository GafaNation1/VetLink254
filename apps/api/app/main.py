# apps/api/app/main.py — FastAPI application entrypoint with health check and v1 routers
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.v1 import users, clinics, bookings, verification, match, kvb, notify, auth

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="VetLink254 Core API — single source of truth for USSD and web front doors.",
)

# Browser CORS for the apps/web dashboard (a different origin than this API). Dev/demo default "*"
# (see config.py CORS_ORIGINS) — restrict to an explicit origin allow-list before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

# Serve locally-stored KYC documents back at /uploads (the R2 path stores full URLs instead).
# The local-disk fallback dir is created by the storage client at import; check again here so the
# mount never fails on a fresh checkout.
os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.LOCAL_UPLOAD_DIR), name="uploads")

# NOTE: Alembic migrations (not create_all) are the schema source of truth. Migrations + admin
# seeding run automatically as part of the start/release command in docker-compose and render.yaml —
# the startup event below intentionally does NOT touch the schema.

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}

app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(clinics.router, prefix=settings.API_V1_STR)
app.include_router(bookings.router, prefix=settings.API_V1_STR)
app.include_router(verification.router, prefix=settings.API_V1_STR)
app.include_router(match.router, prefix=settings.API_V1_STR)
app.include_router(kvb.router, prefix=settings.API_V1_STR)
app.include_router(notify.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)