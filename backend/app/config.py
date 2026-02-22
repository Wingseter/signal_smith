from functools import lru_cache
from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "signal_smith"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database (MySQL HeatWave)
    database_url: str = "mysql+aiomysql://admin:password@localhost:3306/signal_smith"
    database_sync_url: str = "mysql+pymysql://admin:password@localhost:3306/signal_smith"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kiwoom Securities REST API
    kiwoom_app_key: Optional[str] = None
    kiwoom_secret_key: Optional[str] = None
    kiwoom_account_number: Optional[str] = None
    kiwoom_account_password: str = "0000"  # 모의투자 기본 비밀번호
    kiwoom_base_url: str = "https://mockapi.kiwoom.com"
    kiwoom_ws_url: str = "wss://mockapi.kiwoom.com:10000"
    kiwoom_is_mock: bool = True

    # DART API
    dart_api_key: Optional[str] = None

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-opus-20240229"

    # Google Gemini
    google_api_key: Optional[str] = None
    gemini_model: str = "gemini-pro"

    # News API
    news_api_key: Optional[str] = None

    # Tavily API (심층 분석용)
    tavily_api_key: Optional[str] = None

    # Notification
    slack_webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Trading Settings
    trading_enabled: bool = True
    max_position_size: int = 1000000
    stop_loss_percent: float = 3.0
    take_profit_percent: float = 5.0

    # JWT Settings
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        """Reject insecure defaults when running in production."""
        if not self.is_production:
            return self
        if self.secret_key == "change-me-in-production":
            raise ValueError(
                "SECRET_KEY must be set to a secure random value in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        if self.debug:
            raise ValueError("DEBUG must be False in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
