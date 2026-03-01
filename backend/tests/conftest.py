"""Shared test fixtures.

Pre-mocks heavy dependencies (pydantic, sqlalchemy, fastapi, openai, httpx, celery, etc.)
so tests can run locally without Docker.  This MUST be imported before any app module.
"""

import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ── Pre-mock heavy dependencies that may not be installed in test env ──
# Order matters: mock leaf deps first, then packages that import them.

_MOCK_MODULES = {}


def _ensure_mock(name, mock=None):
    """Register a mock module if the real one is not installed."""
    if name not in sys.modules:
        m = mock if mock is not None else MagicMock()
        sys.modules[name] = m
        _MOCK_MODULES[name] = m
        return m
    return sys.modules[name]


# --- pydantic / pydantic_settings ---
_pydantic = _ensure_mock("pydantic")
_pydantic.model_validator = lambda *a, **kw: (lambda f: f)  # decorator no-op
_pydantic.Field = MagicMock()
_pydantic.BaseModel = type("BaseModel", (), {})

_pydantic_settings = _ensure_mock("pydantic_settings")


class _FakeBaseSettings:
    model_config = {}

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


_pydantic_settings.BaseSettings = _FakeBaseSettings
_pydantic_settings.SettingsConfigDict = lambda **kw: {}

# --- sqlalchemy ---
_sa = _ensure_mock("sqlalchemy")
_sa_orm = _ensure_mock("sqlalchemy.orm")
_sa_ext = _ensure_mock("sqlalchemy.ext")
_sa_ext_async = _ensure_mock("sqlalchemy.ext.asyncio")

# Make DeclarativeBase a real class so models can inherit
class _FakeBase:
    __tablename__ = ""
    __table__ = MagicMock()
    metadata = MagicMock()

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

_sa_orm.DeclarativeBase = _FakeBase
_sa_orm.Mapped = MagicMock()
_sa_orm.mapped_column = lambda *a, **kw: None
_sa_orm.relationship = lambda *a, **kw: None
_sa_orm.Session = MagicMock()
_sa_orm.sessionmaker = MagicMock()
_sa.create_engine = MagicMock()
_sa.Column = MagicMock()
_sa.Integer = MagicMock()
_sa.String = MagicMock()
_sa.DateTime = MagicMock()
_sa.Date = MagicMock()
_sa.ForeignKey = MagicMock()
_sa.JSON = MagicMock()
_sa.Numeric = MagicMock()
_sa.func = MagicMock()
_sa.select = MagicMock()
_sa.Float = MagicMock()
_sa.Boolean = MagicMock()
_sa.Text = MagicMock()
_sa.Table = MagicMock()
_sa.MetaData = MagicMock()
_sa_ext_async.AsyncSession = MagicMock()
_sa_ext_async.async_sessionmaker = MagicMock()
_sa_ext_async.create_async_engine = MagicMock()

# --- redis ---
_redis_mock_module = MagicMock()
_redis_async_mock = MagicMock()
_redis_mock_module.asyncio = _redis_async_mock
_redis_async_mock.Redis = MagicMock
_redis_async_mock.from_url = MagicMock(return_value=AsyncMock())
_redis_mock_module.Redis = MagicMock
_redis_mock_module.from_url = MagicMock(return_value=MagicMock())

_ensure_mock("redis", _redis_mock_module)
_ensure_mock("redis.asyncio", _redis_async_mock)

# --- celery ---
_celery = _ensure_mock("celery")
_celery_schedules = _ensure_mock("celery.schedules")
_celery_schedules.crontab = lambda **kw: MagicMock()


class _FakeCelery:
    conf = MagicMock()

    def __init__(self, *a, **kw):
        self.conf = MagicMock()
        self.conf.beat_schedule = {}
        self.conf.task_routes = {}

    def task(self, *a, **kw):
        def decorator(f):
            f.delay = MagicMock()
            f.apply_async = MagicMock()
            return f
        return decorator


_celery.Celery = _FakeCelery

# --- openai ---
_openai = _ensure_mock("openai")
_openai.AsyncOpenAI = MagicMock

# --- httpx ---
_ensure_mock("httpx")

# --- fastapi ---
_fastapi = _ensure_mock("fastapi")
_fastapi.FastAPI = MagicMock
_fastapi.APIRouter = MagicMock
_fastapi.WebSocket = MagicMock
_fastapi.WebSocketDisconnect = type("WebSocketDisconnect", (Exception,), {})
_fastapi.Depends = lambda x: x
_fastapi.HTTPException = type("HTTPException", (Exception,), {"__init__": lambda self, **kw: None})
_fastapi.Request = MagicMock
_fastapi.Response = MagicMock
_fastapi.Query = MagicMock()
_fastapi.Path = MagicMock()
_fastapi.Body = MagicMock()

_fastapi_responses = _ensure_mock("fastapi.responses")
_fastapi_responses.JSONResponse = MagicMock

_fastapi_security = _ensure_mock("fastapi.security")
_fastapi_security.OAuth2PasswordBearer = MagicMock()
_fastapi_security.OAuth2PasswordRequestForm = MagicMock()

_fastapi_middleware = _ensure_mock("fastapi.middleware")
_fastapi_cors = _ensure_mock("fastapi.middleware.cors")
_fastapi_cors.CORSMiddleware = MagicMock

_fastapi_routing = _ensure_mock("fastapi.routing")
_fastapi_routing.APIRoute = MagicMock

# --- starlette ---
_ensure_mock("starlette")
_ensure_mock("starlette.middleware")
_ensure_mock("starlette.middleware.base")

# --- jose ---
_ensure_mock("jose")

# --- aiosqlite ---
_ensure_mock("aiosqlite")

# --- google.generativeai ---
_ensure_mock("google")
_ensure_mock("google.generativeai")

# --- anthropic ---
_ensure_mock("anthropic")

# --- dart_fss ---
_ensure_mock("dart_fss")

# --- aiohttp ---
_ensure_mock("aiohttp")

# --- passlib ---
_ensure_mock("passlib")
_ensure_mock("passlib.context")

# --- python-dotenv ---
_ensure_mock("dotenv")


# ── Fixtures ──

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

    try:
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            yield mock_redis
    except (AttributeError, ModuleNotFoundError):
        # If module hasn't been imported yet, just yield the mock
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
