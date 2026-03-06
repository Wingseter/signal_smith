"""Tests for Kiwoom API response parsers."""

from app.services.kiwoom.parsers import parse_int, parse_float


class TestParseInt:
    def test_basic(self):
        assert parse_int("12345") == 12345

    def test_with_comma(self):
        assert parse_int("1,234,567") == 1234567

    def test_positive_sign(self):
        assert parse_int("+5000") == 5000

    def test_negative_sign(self):
        assert parse_int("-3000") == -3000

    def test_none(self):
        assert parse_int(None) == 0

    def test_empty(self):
        assert parse_int("") == 0

    def test_whitespace(self):
        assert parse_int(" 100 ") == 100

    def test_invalid(self):
        assert parse_int("abc") == 0

    def test_zero(self):
        assert parse_int("0") == 0

    def test_negative_with_comma(self):
        assert parse_int("-1,000") == -1000


class TestParseFloat:
    def test_basic(self):
        assert parse_float("12.34") == 12.34

    def test_signed_negative(self):
        assert parse_float("-5.67") == -5.67

    def test_signed_positive(self):
        assert parse_float("+3.14") == 3.14

    def test_none(self):
        assert parse_float(None) == 0.0

    def test_empty(self):
        assert parse_float("") == 0.0

    def test_invalid(self):
        assert parse_float("abc") == 0.0

    def test_integer_string(self):
        assert parse_float("100") == 100.0

    def test_with_comma(self):
        assert parse_float("1,234.56") == 1234.56
