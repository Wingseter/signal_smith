"""Tests for JWT, password hashing, and token validation."""

import pytest
from unittest.mock import patch

from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_tokens,
    decode_token,
    get_password_hash,
    verify_password,
    TokenData,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "test-password-123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = get_password_hash("correct-password")
        assert not verify_password("wrong-password", hashed)

    def test_different_hashes_for_same_password(self):
        password = "same-password"
        h1 = get_password_hash(password)
        h2 = get_password_hash(password)
        assert h1 != h2  # bcrypt uses random salt


class TestAccessToken:
    def test_create_and_decode(self):
        data = {"sub": "42", "email": "test@example.com"}
        token = create_access_token(data)
        result = decode_token(token, expected_type="access")
        assert result is not None
        assert result.user_id == 42
        assert result.email == "test@example.com"

    def test_missing_sub_returns_none(self):
        data = {"email": "test@example.com"}
        token = create_access_token(data)
        result = decode_token(token, expected_type="access")
        assert result is None

    def test_invalid_token_returns_none(self):
        result = decode_token("invalid.token.string")
        assert result is None

    def test_empty_token_returns_none(self):
        result = decode_token("")
        assert result is None


class TestRefreshToken:
    def test_create_and_decode(self):
        data = {"sub": "7", "email": "user@test.com"}
        token = create_refresh_token(data)
        result = decode_token(token, expected_type="refresh")
        assert result is not None
        assert result.user_id == 7

    def test_refresh_token_rejected_as_access(self):
        """Refresh tokens must not be accepted as access tokens."""
        data = {"sub": "7", "email": "user@test.com"}
        token = create_refresh_token(data)
        result = decode_token(token, expected_type="access")
        assert result is None

    def test_access_token_rejected_as_refresh(self):
        """Access tokens must not be accepted as refresh tokens."""
        data = {"sub": "7", "email": "user@test.com"}
        token = create_access_token(data)
        result = decode_token(token, expected_type="refresh")
        assert result is None


class TestCreateTokens:
    def test_returns_both_tokens(self):
        tokens = create_tokens(user_id=1, email="admin@test.com")
        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.token_type == "bearer"

    def test_access_token_is_valid(self):
        tokens = create_tokens(user_id=99, email="x@y.com")
        data = decode_token(tokens.access_token, expected_type="access")
        assert data is not None
        assert data.user_id == 99

    def test_refresh_token_is_valid(self):
        tokens = create_tokens(user_id=99, email="x@y.com")
        data = decode_token(tokens.refresh_token, expected_type="refresh")
        assert data is not None
        assert data.user_id == 99
