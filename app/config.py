from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")

    comment_delay_min_seconds: int = Field(default=30, alias="COMMENT_DELAY_MIN_SECONDS")
    comment_delay_max_seconds: int = Field(default=180, alias="COMMENT_DELAY_MAX_SECONDS")
    default_timezone: str = Field(default="UTC", alias="DEFAULT_TIMEZONE")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
