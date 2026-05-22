from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "travel-orchestrator"
    environment: str = "local"
    debug: bool = False
    api_prefix: str = "/api/v1"

    secret_key: str = Field(default="change-me", min_length=8)
    access_token_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "travel_orchestrator"
    postgres_user: str = "travel"
    postgres_password: str = "travel"

    redis_url: RedisDsn = "redis://localhost:6379/0"  # type: ignore[assignment]
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    memory_ttl_seconds: int = 86_400
    tool_timeout_seconds: int = 20
    agent_timeout_seconds: int = 60
    workflow_timeout_seconds: int = 180

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    otel_exporter_otlp_endpoint: str | None = None

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        """Normalize common deployment strings into a boolean debug flag."""

        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> PostgresDsn:
        """Build the async SQLAlchemy PostgreSQL DSN from component settings."""

        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            path=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached process-wide application settings."""

    return Settings()
