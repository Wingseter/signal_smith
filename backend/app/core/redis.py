from typing import Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from app.config import settings

redis_client: Optional[Redis] = None


async def get_redis() -> Redis:
    """Get Redis client instance."""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None


class RedisCache:
    """Redis cache utility class."""

    def __init__(self, client: Redis):
        self.client = client

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None,
    ) -> None:
        """Set value in cache with optional expiration."""
        if expire:
            await self.client.setex(key, expire, value)
        else:
            await self.client.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.client.exists(key) > 0

    async def publish(self, channel: str, message: str) -> None:
        """Publish message to channel."""
        await self.client.publish(channel, message)

    async def subscribe(self, channel: str):
        """Subscribe to channel."""
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
