"""Application-wide exception hierarchy."""


class SignalSmithError(Exception):
    """Base exception for all Signal Smith errors."""

    def __init__(self, message: str = "", code: str = "", http_status_code: int = 500):
        self.message = message
        self.code = code
        self.http_status_code = http_status_code
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


class NotFoundError(SignalSmithError):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(message, code, http_status_code=404)


class ValidationError(SignalSmithError):
    """Request validation error."""

    def __init__(self, message: str = "Validation error", code: str = "VALIDATION_ERROR"):
        super().__init__(message, code, http_status_code=422)
