from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/notification_service"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    API_KEY: str = "super-secret-api-key"

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 3600

    # Idempotency
    IDEMPOTENCY_TTL_HOURS: int = 24

    # Retry / worker
    RETRY_BASE_DELAY_SECONDS: int = 30
    RETRY_MULTIPLIER: int = 4
    MAX_RETRIES: int = 3
    WORKER_CONCURRENCY: int = 4

    # Provider simulation
    PROVIDER_FAILURE_RATE: float = 0.1

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"


settings = Settings()
