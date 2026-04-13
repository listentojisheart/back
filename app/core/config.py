"""
Application configuration loaded from environment variables.
Railway injects these; local dev uses .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    ENV: str = Field(default="development")
    APP_NAME: str = "TK-7 Tacit Knowledge System"
    APP_VERSION: str = "2.0.0"

    # Database (Railway auto-injects DATABASE_URL)
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@localhost:5432/tk7")

    # Redis (Railway auto-injects REDIS_URL)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Security
    SECRET_KEY: str = Field(default="dev-secret-change-in-production-use-openssl-rand-hex-32")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Anthropic
    ANTHROPIC_API_KEY: str = Field(default="")
    ANTHROPIC_MODEL_DEFAULT: str = "claude-sonnet-4-5-20250929"
    ANTHROPIC_MAX_TOKENS: int = 8000

    # CORS
    FRONTEND_ORIGIN: str = Field(default="http://localhost:3000")

    # Rate limiting (per user)
    USER_DAILY_MESSAGE_LIMIT: int = 20
    USER_MONTHLY_MESSAGE_LIMIT: int = 300

    # Global circuit breaker (daily spend cap in USD)
    GLOBAL_DAILY_SPEND_CAP_USD: float = 20.0

    # Invite code
    INVITE_CODE_REQUIRED: bool = True

    # File upload
    MAX_UPLOAD_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB
    ALLOWED_UPLOAD_EXTENSIONS: set = {".pdf", ".docx", ".txt", ".md", ".yaml", ".yml"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
