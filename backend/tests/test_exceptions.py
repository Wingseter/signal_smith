"""Tests for custom exception hierarchy."""

from app.core.exceptions import (
    SignalSmithError,
    KiwoomAPIError,
    DartAPIError,
    TradingError,
    WebSocketError,
    AnalysisError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_base(self):
        for exc_cls in (KiwoomAPIError, DartAPIError, TradingError, WebSocketError, AnalysisError):
            assert issubclass(exc_cls, SignalSmithError)
            assert issubclass(exc_cls, Exception)

    def test_base_has_message_and_code(self):
        e = SignalSmithError("test msg", "TEST_CODE")
        assert e.message == "test msg"
        assert e.code == "TEST_CODE"
        assert str(e) == "test msg"

    def test_kiwoom_defaults(self):
        e = KiwoomAPIError()
        assert "Kiwoom" in e.message
        assert e.code == "KIWOOM_ERROR"

    def test_custom_message(self):
        e = TradingError("Order rejected")
        assert e.message == "Order rejected"

    def test_catchable_as_base(self):
        try:
            raise KiwoomAPIError("test")
        except SignalSmithError as e:
            assert e.code == "KIWOOM_ERROR"
