# apps/ussd/tests/test_session_store.py — RedisSessionStore tested against fakeredis (no Redis server needed)
import pytest

import fakeredis

from app.session_store import RedisSessionStore


@pytest.fixture
def store():
    """A RedisSessionStore whose redis client is a fakeredis FakeRedis (in-memory, no server)."""
    s = RedisSessionStore(url="redis://localhost:6379/0", ttl_seconds=180)
    s._client = fakeredis.FakeRedis(decode_responses=True)
    return s


class TestRedisSessionStore:
    def test_save_and_load_roundtrip(self, store):
        store.save("s1", {"node": "welcome", "context": {"animal_type": "Dog"}})
        assert store.load("s1") == {"node": "welcome", "context": {"animal_type": "Dog"}}

    def test_load_missing_session_returns_none(self, store):
        assert store.load("nope") is None

    def test_load_empty_session_id_returns_none(self, store):
        assert store.load("") is None

    def test_delete_removes_session(self, store):
        store.save("s1", {"node": "welcome"})
        store.delete("s1")
        assert store.load("s1") is None

    def test_save_sets_an_expiry_ttl(self, store):
        store.save("s1", {"node": "welcome"})
        assert store._client.ttl("ussd:session:s1") > 0

    def test_save_refreshes_data_for_existing_key(self, store):
        store.save("s1", {"node": "welcome"})
        store.save("s1", {"node": "location"})
        assert store.load("s1")["node"] == "location"

    def test_corrupt_payload_returns_none(self, store):
        store._client.set("ussd:session:bad", "{not valid json")
        assert store.load("bad") is None

    def test_key_namespace_is_ussd_session_prefix(self, store):
        store.save("s1", {"node": "welcome"})
        assert store._client.exists("ussd:session:s1") == 1
        assert store._client.exists("s1") == 0
