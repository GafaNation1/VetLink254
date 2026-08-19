# apps/ussd/app/session_store.py — Redis-backed USSD session state (node + collected choices) with short TTL; no silent in-memory fallback
import json
import logging
import os

import redis

logger = logging.getLogger("ussd.session_store")

SESSION_TTL_DEFAULT_SECONDS = 180  # USSD sessions are short-lived; keys expire and reset the flow


class SessionStoreError(Exception):
    """Raised when Redis is unreachable — treated as a BLOCKING issue, never silently degraded."""


def _key(session_id: str) -> str:
    return f"ussd:session:{session_id}"


class RedisSessionStore:
    """Persists per-session menu node + collected choices in Redis with an expiring key."""

    def __init__(self, url: str = "", ttl_seconds: int = SESSION_TTL_DEFAULT_SECONDS):
        self.url = url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.ttl = int(os.getenv("SESSION_TTL_SECONDS", str(ttl_seconds)))
        self._client = redis.Redis.from_url(self.url, decode_responses=True)

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError as exc:
            logger.error("BLOCKING ISSUE: Redis unreachable at %s: %s", self.url, exc)
            return False

    def load(self, session_id: str):
        """Return the stored session dict, or None if no live session exists."""
        if not session_id:
            return None
        try:
            raw = self._client.get(_key(session_id))
        except redis.RedisError as exc:
            logger.error("BLOCKING ISSUE: Redis read failed for session %s: %s", session_id, exc)
            raise SessionStoreError("Redis unavailable") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("Corrupt session payload for %s, treating as new session: %s", session_id, exc)
            return None

    def save(self, session_id: str, data: dict) -> None:
        """Persist the session and refresh its TTL on every request (USSD keeps the session alive)."""
        if not session_id:
            return
        try:
            self._client.setex(_key(session_id), self.ttl, json.dumps(data))
        except redis.RedisError as exc:
            logger.error("BLOCKING ISSUE: Redis write failed for session %s: %s", session_id, exc)
            raise SessionStoreError("Redis unavailable") from exc

    def delete(self, session_id: str) -> None:
        if not session_id:
            return
        try:
            self._client.delete(_key(session_id))
        except redis.RedisError as exc:
            logger.error("BLOCKING ISSUE: Redis delete failed for session %s: %s", session_id, exc)
            raise SessionStoreError("Redis unavailable") from exc