from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_env: str = Field(default="development", alias="API_ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/cogniflow",
        alias="DATABASE_URL",
    )
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8001, alias="CHROMA_PORT")
    chroma_collection: str = Field(default="cogniflow-documents", alias="CHROMA_COLLECTION")
    upload_dir: str = Field(default="data/uploads", alias="UPLOAD_DIR")
    web_app_url: str = Field(default="http://localhost:3000", alias="WEB_APP_URL")
    integration_oauth_state_secret: str = Field(
        default="dev-integration-oauth-state-secret",
        alias="INTEGRATION_OAUTH_STATE_SECRET",
    )
    secret_encryption_key: str = Field(
        default="dev-secret-encryption-key-change-me",
        alias="SECRET_ENCRYPTION_KEY",
    )
    google_oauth_client_id: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str | None = Field(
        default=None,
        alias="GOOGLE_OAUTH_CLIENT_SECRET",
    )
    worker_inline_execution: bool = Field(default=True, alias="WORKER_INLINE_EXECUTION")
    worker_poll_interval_seconds: float = Field(default=2.0, alias="WORKER_POLL_INTERVAL_SECONDS")
    worker_queue_name: str | None = Field(default=None, alias="WORKER_QUEUE_NAME")
    intelligence_autoschedule_enabled: bool = Field(
        default=True,
        alias="INTELLIGENCE_AUTOSCHEDULE_ENABLED",
    )
    intelligence_autoschedule_interval_seconds: float = Field(
        default=60.0,
        alias="INTELLIGENCE_AUTOSCHEDULE_INTERVAL_SECONDS",
    )
    intelligence_autoschedule_batch_size: int = Field(
        default=50,
        alias="INTELLIGENCE_AUTOSCHEDULE_BATCH_SIZE",
    )
    intelligence_monitoring_queue_name: str = Field(
        default="monitoring",
        alias="INTELLIGENCE_MONITORING_QUEUE_NAME",
    )
    intelligence_default_alert_threshold: str = Field(
        default="medium",
        alias="INTELLIGENCE_DEFAULT_ALERT_THRESHOLD",
    )
    ops_queue_backlog_warning_threshold: int = Field(
        default=25,
        alias="OPS_QUEUE_BACKLOG_WARNING_THRESHOLD",
    )
    ops_queue_lag_warning_seconds: int = Field(
        default=300,
        alias="OPS_QUEUE_LAG_WARNING_SECONDS",
    )
    ops_job_failure_rate_warning: float = Field(
        default=0.2,
        alias="OPS_JOB_FAILURE_RATE_WARNING",
    )
    ops_latency_p95_warning_ms: float = Field(
        default=5000.0,
        alias="OPS_LATENCY_P95_WARNING_MS",
    )
    api_cors_allow_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="API_CORS_ALLOW_ORIGINS",
    )

    @field_validator("api_cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value: object) -> object:
        if isinstance(value, str):
            # Support comma-separated env format for local developer ergonomics.
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
