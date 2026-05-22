from collections.abc import AsyncIterator

from redis.asyncio import Redis

from app.core.config import get_settings


settings = get_settings()
redis_client = Redis.from_url(str(settings.redis_url), decode_responses=True)


async def get_redis() -> AsyncIterator[Redis]:
    """Yield the shared async Redis client for dependency injection."""

    yield redis_client
