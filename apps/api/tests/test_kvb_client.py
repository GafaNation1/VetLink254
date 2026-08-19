# apps/api/tests/test_kvb_client.py — KVBVerificationClient: stub mode (active/expired/not-found),
# stub WARNING logging, per-session Redis caching, and the real-mode HTTP path (via httpx.MockTransport)
import json
import logging

import httpx
import pytest

import redis
from app.integrations.kvb_client import (
    KVBVerificationClient,
    KVBVerificationError,
    KVBNotFoundError,
    _cache_key,
)


class FakeRedis:
    """Dict-backed stand-in for the real Redis client (get/setex only, no server needed)."""

    def __init__(self):
        self._d = {}

    def get(self, key):
        return self._d.get(key)

    def setex(self, key, ttl, value):
        self._d[key] = value


class FailingRedis:
    """Redis stand-in whose calls always raise — proves graceful degradation to an uncached call."""

    def get(self, key):
        raise redis.ConnectionError("no server")

    def setex(self, key, ttl, value):
        raise redis.ConnectionError("no server")


class TestStubMode:
    def test_active_license(self):
        client = KVBVerificationClient()
        result = client.verify_license("KVB-1001")
        assert result == {
            "status": "active",
            "name": "Dr. Wanjiku Kamau",
            "license_type": "Veterinary Surgeon",
        }

    def test_expired_license(self):
        client = KVBVerificationClient()
        result = client.verify_license("KVB-1003")
        assert result["status"] == "expired"
        assert result["name"] == "Dr. Grace Muthoni"

    def test_unknown_license_raises_not_found(self):
        client = KVBVerificationClient()
        with pytest.raises(KVBNotFoundError):
            client.verify_license("KVB-9999")

    def test_blank_license_raises_error(self):
        client = KVBVerificationClient()
        with pytest.raises(KVBVerificationError):
            client.verify_license("   ")

    def test_stub_use_logs_warning(self, caplog):
        client = KVBVerificationClient()
        with caplog.at_level(logging.WARNING, logger="app.integrations.kvb_client"):
            client.verify_license("KVB-1001")
        assert any("STUB" in r.message and "NOT a real KVB integration" in r.message for r in caplog.records)


class TestCaching:
    def test_successful_result_is_cached_and_served_from_cache(self):
        fake_redis = FakeRedis()
        client = KVBVerificationClient(cache_ttl=180, redis_client=fake_redis)
        hits = []

        def fake_fetch(ln):
            hits.append(ln)
            return {"status": "active", "name": "Dr. Cache", "license_type": "Veterinary Surgeon"}

        client._fetch = fake_fetch  # substitute the fetch path so the cache behavior is isolated
        first = client.verify_license("KVB-C1")
        second = client.verify_license("KVB-C1")
        assert first == second == {"status": "active", "name": "Dr. Cache", "license_type": "Veterinary Surgeon"}
        assert hits == ["KVB-C1"]  # second call served from cache, no second fetch
        assert fake_redis.get(_cache_key("KVB-C1")) == json.dumps(first)

    def test_cache_disabled_when_ttl_zero(self):
        fake_redis = FakeRedis()
        client = KVBVerificationClient(cache_ttl=0, redis_client=fake_redis)
        hits = []

        def fake_fetch(ln):
            hits.append(ln)
            return {"status": "active", "name": "Dr. NoCache", "license_type": "Veterinary Surgeon"}

        client._fetch = fake_fetch
        client.verify_license("KVB-C2")
        client.verify_license("KVB-C2")
        assert len(hits) == 2  # no caching at all
        assert fake_redis.get(_cache_key("KVB-C2")) is None

    def test_redis_failure_degrades_to_uncached_call(self):
        client = KVBVerificationClient(cache_ttl=180, redis_client=FailingRedis())
        result = client.verify_license("KVB-1002")
        assert result["status"] == "active"  # still works without Redis


class TestRealModeHTTP:
    def _make_transport(self, requests_log, verify_body=None, token_body=None, verify_status=200):
        def handler(request):
            requests_log.append(request)
            if request.url.path == "/oauth/token":
                return httpx.Response(200, json=token_body or {"access_token": "tok-123"})
            if request.url.path.startswith("/api/v1/verify/"):
                return httpx.Response(verify_status, json=verify_body or {"status": "active", "name": "Dr. Real", "license_type": "Veterinary Surgeon"})
            return httpx.Response(500)

        return httpx.MockTransport(handler)

    def test_oauth_flow_with_client_credentials(self):
        log = []
        transport = self._make_transport(log)
        client = KVBVerificationClient(
            base_url="https://kvb.example.com", client_id="cid", client_secret="csecret", transport=transport
        )
        result = client.verify_license("KVB-2001")
        assert result["status"] == "active"
        token_req = log[0]
        assert token_req.url.path == "/oauth/token"
        body = token_req.content.decode()
        assert "grant_type=client_credentials" in body
        assert "client_id=cid" in body
        assert "client_secret=csecret" in body
        verify_req = log[1]
        assert verify_req.url.path == "/api/v1/verify/KVB-2001"
        assert verify_req.headers["Authorization"] == "Bearer tok-123"

    def test_not_found_raises_kvb_not_found(self):
        log = []
        transport = self._make_transport(log, verify_status=404)
        client = KVBVerificationClient(base_url="https://kvb.example.com", transport=transport)
        with pytest.raises(KVBNotFoundError):
            client.verify_license("KVB-9999")

    def test_server_error_raises_kvb_error(self):
        log = []
        transport = self._make_transport(log, verify_status=500)
        client = KVBVerificationClient(base_url="https://kvb.example.com", transport=transport)
        with pytest.raises(KVBVerificationError):
            client.verify_license("KVB-2001")

    def test_missing_access_token_raises_kvb_error(self):
        log = []
        transport = self._make_transport(log, token_body={"error": "invalid_client"})
        client = KVBVerificationClient(base_url="https://kvb.example.com", transport=transport)
        with pytest.raises(KVBVerificationError):
            client.verify_license("KVB-2001")
