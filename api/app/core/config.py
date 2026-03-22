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
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    chat_model: str = Field(default="gpt-4o", alias="CHAT_MODEL")
    fallback_chat_model: str = Field(default="gpt-4o-mini", alias="FALLBACK_CHAT_MODEL")
    gemini_chat_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_CHAT_MODEL")
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8001, alias="CHROMA_PORT")
    chroma_collection: str = Field(default="cogniflow-documents", alias="CHROMA_COLLECTION")
    upload_dir: str = Field(default="data/uploads", alias="UPLOAD_DIR")
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
