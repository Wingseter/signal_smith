"""Tests for common validation utilities."""

import pytest
from fastapi import HTTPException

from app.core.validators import validate_symbol


class TestValidateSymbol:
    def test_valid_symbol(self):
        assert validate_symbol("005930") == "005930"

    def test_short_symbol(self):
        with pytest.raises(HTTPException):
            validate_symbol("0059")

    def test_alpha_symbol(self):
        with pytest.raises(HTTPException):
            validate_symbol("00593A")

    def test_empty_symbol(self):
        with pytest.raises(HTTPException):
            validate_symbol("")

    def test_long_symbol(self):
        with pytest.raises(HTTPException):
            validate_symbol("0059301")

    def test_valid_etf(self):
        assert validate_symbol("069500") == "069500"
