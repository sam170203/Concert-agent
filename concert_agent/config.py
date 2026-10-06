from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./concert_agent.db"
    dry_run: bool = True
    cron_secret: str = "change-me"

    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_verify_token: str = "change-me-too"
    whatsapp_app_secret: str | None = None
    whatsapp_api_version: str = "v23.0"

    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
