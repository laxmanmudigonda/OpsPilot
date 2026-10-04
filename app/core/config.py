from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OpsPilot"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./opspilot.db"
    redis_url: str = "redis://localhost:6379/0"
    api_key: str = Field(default="development-only-key", min_length=8)
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_incident_channel_id: str = ""
    github_webhook_secret: str = ""
    github_token: str = ""
    monitor_interval: int = Field(default=30, ge=5)
    monitor_timeout: float = Field(default=5, ge=0.5, le=30)
    auto_incident_on_deploy_failure: bool = True
    ai_provider: str = "disabled"
    ai_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
