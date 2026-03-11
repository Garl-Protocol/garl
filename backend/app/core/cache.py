"""
GARL Protocol — Redis cache layer with graceful fallback.

If REDIS_URL is not set, all operations silently return None (no-op).
This allows the app to run without Redis in development.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_redis_client = None
_redis_available = False


def _get_redis():
    global _redis_client, _redis_available
    if _redis_client is not None:
        return _redis_client if _redis_available else None

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        _redis_available = False
        _redis_client = False
        return None

    try:
        import redis
        _redis_client = redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
        _redis_client.ping()
        _redis_available = True
        logger.info("Redis connected: %s", redis_url[:30] + "...")
        return _redis_client
    except Exception as e:
        logger.warning("Redis not available, running without cache: %s", e)
        _redis_available = False
        _redis_client = False
        return None


def cache_get(key: str) -> Any | None:
    r = _get_redis()
    if not r:
        return None
    try:
        data = r.get(f"garl:{key}")
        return json.loads(data) if data else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    r = _get_redis()
    if not r:
        return False
    try:
        r.setex(f"garl:{key}", ttl, json.dumps(value, default=str))
        return True
    except Exception:
        return False


def cache_delete(key: str) -> bool:
    r = _get_redis()
    if not r:
        return False
    try:
        r.delete(f"garl:{key}")
        return True
    except Exception:
        return False


def cache_delete_pattern(pattern: str) -> int:
    r = _get_redis()
    if not r:
        return 0
    try:
        keys = r.keys(f"garl:{pattern}")
        if keys:
            return r.delete(*keys)
        return 0
    except Exception:
        return 0
