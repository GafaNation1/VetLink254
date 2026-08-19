# apps/api/app/integrations/storage_client.py — KYC file storage: Cloudflare R2 (S3-compatible) with local-disk fallback
#
# PART 4 of the demo-readiness pass. Document submission now uploads a real multipart file; this
# module stores the bytes and returns a URL kept in the existing verification_documents.file_url
# column (no schema change needed — it already holds a URL string).
#
# BACKEND SELECTION:
#   - R2 is used when R2_ENDPOINT_URL + R2_ACCESS_KEY_ID + R2_SECRET_ACCESS_KEY + R2_BUCKET_NAME are
#     ALL set (boto3 against an S3-compatible endpoint).
#   - Otherwise we fall back to LOCAL DISK (LOCAL_UPLOAD_DIR) so the local demo's document submission
#     keeps working with zero external credentials. The API serves those files back at /uploads.
#
# CODE COMPLETE — NOT yet live-verified against a real R2 bucket (pending: real Cloudflare R2 account,
# bucket, API token and public URL). boto3 is a hard runtime dep (pinned in requirements.txt).
import logging
import os
from uuid import uuid4

from app.config import settings

logger = logging.getLogger("app.integrations.storage_client")

# File-type allowlist (images + PDF). A mismatched MIME type is rejected before any storage write.
ALLOWED_DOC_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
}
ALLOWED_DOC_TYPE_HINT = "PNG/JPEG/WebP images and PDF files"

DEFAULT_MAX_BYTES = 10 * 1024 * 1024


def max_upload_bytes() -> int:
    return max(1, settings.DOC_UPLOAD_MAX_MB) * 1024 * 1024


class StorageError(Exception):
    """Raised when a file cannot be stored. The upload endpoint turns this into a 5xx."""


class StorageClient:
    """Single public method: upload_file(bytes, filename, content_type) -> URL string (never raises)."""

    def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        raise NotImplementedError  # pragma: no cover — subclasses implement this


class LocalStorageClient(StorageClient):
    """Writes files to LOCAL_UPLOAD_DIR (served back by the API at /uploads). Used when R2 is unset."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = os.path.abspath(base_dir or settings.LOCAL_UPLOAD_DIR)
        self.kyc_dir = os.path.join(self.base_dir, "kyc")
        os.makedirs(self.kyc_dir, exist_ok=True)
        logger.info("KYC file storage: LOCAL DISK at %s (R2 not configured)", self.kyc_dir)

    def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        safe_name = os.path.basename(filename or "document")
        object_key = f"{uuid4().hex}/{safe_name}"
        dest = os.path.join(self.kyc_dir, object_key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(file_bytes)
        relative = os.path.join("kyc", object_key).replace(os.sep, "/")
        return f"/uploads/{relative}"


class R2StorageClient(StorageClient):
    """Cloudflare R2 via boto3 (S3-compatible). `client` is injectable for tests (no real network)."""

    def __init__(self, boto3_session=None, client=None):
        import boto3  # hard runtime dep (pinned)

        if client is not None:
            self._client = client
        else:
            session = boto3_session or boto3.session.Session()
            self._client = session.client(
                "s3",
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",  # R2 requires region "auto"
            )
        self.bucket = settings.R2_BUCKET_NAME
        self.public_base_url = (settings.R2_PUBLIC_BASE_URL or "").rstrip("/")
        logger.info("KYC file storage: Cloudflare R2 bucket=%s endpoint=%s", self.bucket, settings.R2_ENDPOINT_URL)

    def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        safe_name = os.path.basename(filename or "document")
        object_key = f"kyc/{uuid4().hex}/{safe_name}"
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=file_bytes,
                ContentType=content_type,
            )
        except Exception as exc:
            logger.error("BLOCKING ISSUE: R2 put_object failed for key %s: %s", object_key, exc)
            raise StorageError(f"R2 upload failed: {exc}") from exc
        if self.public_base_url:
            return f"{self.public_base_url}/{object_key}"
        return f"{settings.R2_ENDPOINT_URL.rstrip('/')}/{self.bucket}/{object_key}"


def r2_configured() -> bool:
    return bool(
        settings.R2_ENDPOINT_URL
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_BUCKET_NAME
    )


def get_storage_client() -> StorageClient:
    return R2StorageClient() if r2_configured() else LocalStorageClient()


# One shared client for the whole process (the verification router uses this).
storage_client = get_storage_client()