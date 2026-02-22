"""Application-wide exception hierarchy."""


class SignalSmithError(Exception):
    """Base exception for all Signal Smith errors."""

    def __init__(self, message: str = "", code: str = ""):
        self.message = message
        self.code = code
        super().__init__(message)


class KiwoomAPIError(SignalSmithError):
    """Kiwoom Securities API errors."""

    def __init__(self, message: str = "Kiwoom API error", code: str = "KIWOOM_ERROR"):
        super().__init__(message, code)


class DartAPIError(SignalSmithError):
    """DART electronic disclosure API errors."""

    def __init__(self, message: str = "DART API error", code: str = "DART_ERROR"):
        super().__init__(message, code)


class TradingError(SignalSmithError):
    """Trading execution errors."""

    def __init__(self, message: str = "Trading error", code: str = "TRADING_ERROR"):
        super().__init__(message, code)


class WebSocketError(SignalSmithError):
    """WebSocket communication errors."""

    def __init__(self, message: str = "WebSocket error", code: str = "WS_ERROR"):
        super().__init__(message, code)


class AnalysisError(SignalSmithError):
    """AI analysis pipeline errors."""

    def __init__(self, message: str = "Analysis error", code: str = "ANALYSIS_ERROR"):
        super().__init__(message, code)
