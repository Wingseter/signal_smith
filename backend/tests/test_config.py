"""Tests for Settings validation."""

import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError

from app.config import Settings


# Prevent .env file from leaking into tests
@pytest.fixture(autouse=True)
def _isolate_from_env(monkeypatch, tmp_path):
    """Ensure tests use class defaults, not values from .env."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)


class TestSettingsDefaults:
    def test_default_is_development(self):
        s = Settings(_env_file=None)
        assert s.app_env == "development"
        assert not s.is_production

    def test_default_secret_key_allowed_in_dev(self):
        """Default secret key is acceptable in non-production."""
        s = Settings(_env_file=None, app_env="development")
        assert s.secret_key == "change-me-in-production"

    def test_cors_origins_have_localhost(self):
        s = Settings(_env_file=None)
        assert "http://localhost:3000" in s.cors_origins


class TestProductionValidation:
    def test_rejects_default_secret_key(self):
        with pytest.raises(ValidationError, match="SECRET_KEY"):
            Settings(_env_file=None, app_env="production", debug=False)

    def test_rejects_debug_true(self):
        with pytest.raises(ValidationError, match="DEBUG"):
            Settings(
                _env_file=None,
                app_env="production",
                secret_key="a-real-secret-key-for-production-use",
                debug=True,
            )

    def test_accepts_valid_production_config(self):
        s = Settings(
            _env_file=None,
            app_env="production",
            secret_key="a-real-secret-key-for-production-use",
            debug=False,
        )
        assert s.is_production
        assert s.secret_key == "a-real-secret-key-for-production-use"


class TestJWTSettings:
    def test_default_algorithm(self):
        s = Settings(_env_file=None)
        assert s.algorithm == "HS256"

    def test_default_token_expiry(self):
        s = Settings(_env_file=None)
        assert s.access_token_expire_minutes == 30
        assert s.refresh_token_expire_days == 7
