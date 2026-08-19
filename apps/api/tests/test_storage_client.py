# apps/api/tests/test_storage_client.py — PART 4 storage: local-disk fallback + R2 (S3-compatible) via a fake boto3 client
import os

import pytest

from app.integrations import storage_client
from app.integrations.storage_client import (
    ALLOWED_DOC_TYPES,
    LocalStorageClient,
    R2StorageClient,
    max_upload_bytes,
)


class TestAllowlist:
    def test_images_and_pdf_allowed(self):
        assert ALLOWED_DOC_TYPES == {
            "image/png",
            "image/jpeg",
            "image/webp",
            "application/pdf",
        }

    def test_default_max_size_is_10mb(self):
        assert max_upload_bytes() == 10 * 1024 * 1024


class TestLocalStorageClient:
    def test_uploads_bytes_and_returns_servable_url(self, tmp_path):
        client = LocalStorageClient(base_dir=str(tmp_path))
        url = client.upload_file(b"%PDF-1.4 fake", "licence.pdf", "application/pdf")
        assert url.startswith("/uploads/kyc/")
        assert url.endswith("/licence.pdf")
        # The bytes actually landed on disk under the same path.
        relative = url.removeprefix("/uploads/")
        stored = tmp_path / relative
        assert stored.read_bytes() == b"%PDF-1.4 fake"

    def test_filenames_are_basename_sanitised(self, tmp_path):
        client = LocalStorageClient(base_dir=str(tmp_path))
        url = client.upload_file(b"data", "../../evil.pdf", "application/pdf")
        assert "/evil.pdf" in url
        assert "../" not in url

    def test_each_upload_gets_a_unique_key(self, tmp_path):
        client = LocalStorageClient(base_dir=str(tmp_path))
        a = client.upload_file(b"a", "a.pdf", "application/pdf")
        b = client.upload_file(b"a", "a.pdf", "application/pdf")
        assert a != b


class FakeBoto3Client:
    """Minimal in-memory stand-in for a boto3 s3 client — records put_object calls, never touches the network."""

    def __init__(self):
        self.puts = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


class TestR2StorageClient:
    def test_uses_r2_when_all_vars_set(self, monkeypatch):
        monkeypatch.setattr(storage_client.settings, "R2_ENDPOINT_URL", "https://x.r2.cloudflarestorage.com")
        monkeypatch.setattr(storage_client.settings, "R2_ACCESS_KEY_ID", "ak")
        monkeypatch.setattr(storage_client.settings, "R2_SECRET_ACCESS_KEY", "sk")
        monkeypatch.setattr(storage_client.settings, "R2_BUCKET_NAME", "vetlink-kyc")
        assert storage_client.r2_configured() is True
        assert isinstance(storage_client.get_storage_client(), R2StorageClient)

    def test_falls_back_to_local_when_r2_unset(self, monkeypatch):
        monkeypatch.setattr(storage_client.settings, "R2_ENDPOINT_URL", "")
        monkeypatch.setattr(storage_client.settings, "R2_BUCKET_NAME", "")
        assert storage_client.r2_configured() is False
        client = storage_client.get_storage_client()
        assert isinstance(client, LocalStorageClient)

    def test_put_object_shape_and_url_with_public_base(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage_client.settings, "R2_BUCKET_NAME", "vetlink-kyc")
        monkeypatch.setattr(storage_client.settings, "R2_PUBLIC_BASE_URL", "https://pub.example.r2.dev")
        fake = FakeBoto3Client()
        client = R2StorageClient(client=fake)
        url = client.upload_file(b"%PDF-1.4", "licence.pdf", "application/pdf")
        assert url.startswith("https://pub.example.r2.dev/kyc/")
        assert url.endswith("/licence.pdf")
        assert len(fake.puts) == 1
        put = fake.puts[0]
        assert put["Bucket"] == "vetlink-kyc"
        assert put["Body"] == b"%PDF-1.4"
        assert put["ContentType"] == "application/pdf"
        assert put["Key"].startswith("kyc/")

    def test_url_from_s3_endpoint_when_no_public_base(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage_client.settings, "R2_BUCKET_NAME", "vetlink-kyc")
        monkeypatch.setattr(storage_client.settings, "R2_PUBLIC_BASE_URL", "")
        fake = FakeBoto3Client()
        client = R2StorageClient(client=fake)
        url = client.upload_file(b"data", "a.png", "image/png")
        assert url.endswith("/a.png")

    def test_storage_failure_raises_storage_error(self, tmp_path, monkeypatch):
        class BoomClient:
            def put_object(self, **kwargs):
                raise RuntimeError("network down")

        monkeypatch.setattr(storage_client.settings, "R2_BUCKET_NAME", "vetlink-kyc")
        client = R2StorageClient(client=BoomClient())
        with pytest.raises(storage_client.StorageError):
            client.upload_file(b"data", "a.png", "image/png")