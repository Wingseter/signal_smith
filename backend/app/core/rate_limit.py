"""Redis-based rate limiter for API endpoints."""

import logging

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter backed by Redis.

    Usage as a FastAPI dependency::

        limiter = RateLimiter(max_requests=10, window_seconds=60)

        @router.post("/login")
        async def login(request: Request, _: None = Depends(limiter)):
            ...
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _key(self, request: Request, prefix: str = "rl") -> str:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        return f"{prefix}:{path}:{client_ip}"

    async def __call__(self, request: Request) -> None:
        key = self._key(request)
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, self.window_seconds)
            if current > self.max_requests:
                ttl = await redis.ttl(key)
                logger.warning(
                    "Rate limit exceeded: %s (%d/%d, resets in %ds)",
                    key,
                    current,
                    self.max_requests,
                    max(ttl, 0),
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {max(ttl, 1)} seconds.",
                )
        except HTTPException:
            raise
        except Exception as exc:
            # If Redis is unavailable, allow the request through
            logger.debug("Rate limiter Redis error (allowing request): %s", exc)
