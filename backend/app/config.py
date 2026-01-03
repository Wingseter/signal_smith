from functools import lru_cache
from typing import Optional

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

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/signal_smith"
    database_sync_url: str = "postgresql://postgres:postgres@localhost:5432/signal_smith"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Korea Investment Securities API
    kis_app_key: Optional[str] = None
    kis_app_secret: Optional[str] = None
    kis_account_number: Optional[str] = None
    kis_account_product_code: str = "01"
    kis_base_url: str = "https://openapi.koreainvestment.com:9443"
    kis_ws_url: str = "ws://ops.koreainvestment.com:21000"

    # Kiwoom Securities API
    kiwoom_user_id: Optional[str] = None
    kiwoom_user_password: Optional[str] = None
    kiwoom_cert_password: Optional[str] = None

    # DART API
    dart_api_key: Optional[str] = None

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"

    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-opus-20240229"

    # Google Gemini
    google_api_key: Optional[str] = None
    gemini_model: str = "gemini-pro"

    # News API
    news_api_key: Optional[str] = None

    # Notification
    slack_webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Trading Settings
    trading_enabled: bool = False
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
