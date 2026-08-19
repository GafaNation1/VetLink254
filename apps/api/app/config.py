# apps/api/app/config.py — Application configuration management using Pydantic Settings
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "VetLink254 Core API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://vetlink:vetlink_pass@localhost:5432/vetlink254")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod-0123456789abcdef")

    # Minimal real auth (JWT, PART 3 of the demo-readiness pass — replaces the shared X-Admin-Token).
    # One admin user is seeded idempotently from env vars (apps/api/scripts/create_admin.py, run by the
    # docker-compose api start command and the Render release command) and logs in via
    # POST /api/v1/auth/login -> a short-lived HS256 JWT (Bearer) required on POST /clinics/{id}/verify
    # and PATCH /clinics/{id}. ADMIN_PASSWORD unset => NO admin seeded => login has nobody to succeed for
    # (production must set it explicitly; the dev defaults below are LOCAL-DEMO-ONLY placeholders).
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    # JWT lifetime in minutes. No refresh tokens by design (documented MVP-auth decision).
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # Browser access to the public read-only endpoints for the apps/web dashboard (GET /clinics etc.).
    # Dev default "*" (read-only GET + the POST/PATCH the demo uses); a comma-separated allow-list
    # should be set in production. Logged as a dev/demo default in docs/progress/LOG.md.
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # KVB (Kenya Veterinary Board) license-verification bridge.
    # VetLink254 is NOT the source of truth on who is a licensed vet — KVB is. We call OUT to KVB's
    # system (MMS at mms.kenyavetboard.or.ke) once they expose a public API. Until then the client
    # runs in TEMPORARY STUB MODE (default: unset or "stub") returning canned data and logging a
    # WARNING on every use — it must never be mistaken for a real integration.
    KVB_API_BASE_URL: str = os.getenv("KVB_API_BASE_URL", "stub")
    # Dev placeholders ONLY — replace with real KVB OAuth2 client-credentials in production.
    KVB_CLIENT_ID: str = os.getenv("KVB_CLIENT_ID", "kvb-dev-client-id")
    KVB_CLIENT_SECRET: str = os.getenv("KVB_CLIENT_SECRET", "kvb-dev-client-secret")
    # Per-session Redis cache TTL for successful license lookups (matches the 180s USSD session TTL);
    # <= 0 disables caching. License status is ALWAYS re-checked live per session — never persisted to Postgres.
    KVB_CACHE_TTL_SECONDS: int = int(os.getenv("KVB_CACHE_TTL_SECONDS", "180"))

    # Africa's Talking SMS (notifications), via the official africastalking SDK (pinned 2.0.3).
    # SMSClient runs in STUB/no-op mode (logs a WARNING, skips sending) until AT_USERNAME +
    # AT_API_KEY are set — a missing SMS config must never break the booking/verify flow.
    # SANDBOX CONVENTION: username "sandbox" makes the SDK route to api.sandbox.africastalking.com
    # automatically (the SDK hardcodes base URLs, so the old AT_SMS_BASE_URL override is gone).
    # BOARD_NOTIFICATION_PHONE receives a summary of every vet-verification lookup / clinic KYC
    # event: a minimal SMS stand-in for the board/reporting layer (not yet built), not the real thing.
    AT_USERNAME: str = os.getenv("AT_USERNAME", "")
    AT_API_KEY: str = os.getenv("AT_API_KEY", "")
    AT_SENDER_ID: str = os.getenv("AT_SENDER_ID", "")  # optional shortcode/alphanumeric sender
    BOARD_NOTIFICATION_PHONE: str = os.getenv("BOARD_NOTIFICATION_PHONE", "")

    # KYC document storage (PART 4). Real uploads go to Cloudflare R2 (S3-compatible) via boto3 when
    # the R2_* vars are ALL set; otherwise we fall back to LOCAL DISK storage (LOCAL_UPLOAD_DIR,
    # served back by the API at /uploads) so the local demo's document submission keeps working with
    # zero external credentials. CODE COMPLETE — NOT yet live-verified against a real R2 bucket
    # (pending: real R2 account + bucket + credentials).
    R2_ENDPOINT_URL: str = os.getenv("R2_ENDPOINT_URL", "")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "")
    # Optional public URL prefix for the bucket (e.g. https://pub-XXXX.r2.dev). If unset we build the
    # object URL from the S3 endpoint + bucket (private/signed-URL territory — see LOG.md).
    R2_PUBLIC_BASE_URL: str = os.getenv("R2_PUBLIC_BASE_URL", "")
    # Local-disk fallback directory (also served by the API at /uploads in local/dev runs).
    LOCAL_UPLOAD_DIR: str = os.getenv("LOCAL_UPLOAD_DIR", "uploads")
    # Max accepted KYC file size in MB (allowlist enforced in app/integrations/storage_client.py).
    DOC_UPLOAD_MAX_MB: int = int(os.getenv("DOC_UPLOAD_MAX_MB", "10"))

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()