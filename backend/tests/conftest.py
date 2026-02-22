"""Shared test fixtures."""

import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Pre-mock heavy dependencies that may not be installed in test env ──
# This must happen before any app module is imported.

_redis_mock_module = MagicMock()
_redis_async_mock = MagicMock()
_redis_mock_module.asyncio = _redis_async_mock
_redis_async_mock.Redis = MagicMock
_redis_async_mock.from_url = MagicMock(return_value=AsyncMock())

if "redis" not in sys.modules:
    sys.modules["redis"] = _redis_mock_module
    sys.modules["redis.asyncio"] = _redis_async_mock


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _mock_redis():
    """Globally mock Redis to avoid real connections during tests."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.exists = AsyncMock(return_value=0)
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.publish = AsyncMock(return_value=1)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.ttl = AsyncMock(return_value=-2)

    with patch("app.core.redis.get_redis", return_value=mock_redis):
        yield mock_redis


@pytest.fixture()
def settings_override():
    """Override settings for testing."""
    from app.config import Settings

    return Settings(
        app_env="testing",
        secret_key="test-secret-key-not-for-production",
        database_url="sqlite+aiosqlite:///test.db",
        database_sync_url="sqlite:///test.db",
        redis_url="redis://localhost:6379/15",
    )
