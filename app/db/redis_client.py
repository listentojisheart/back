"""
Redis client for rate limiting, circuit breaker, and token caching.
"""
import redis
from app.core.config import settings


_redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=20,
)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_redis_pool)
