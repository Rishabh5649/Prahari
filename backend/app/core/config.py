"""Application configuration via environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads all configuration from environment variables / .env file."""

    DATABASE_URL: str = "postgresql+asyncpg://prahari:prahari@localhost:5432/prahari"
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    MODEL: str = "gemini-2.5-flash"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "prahari-evidence"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        # Fix scheme
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Strip sslmode query param — asyncpg ignores it and it
        # causes warnings; SSL is passed via connect_args instead
        if "?sslmode=" in v:
            v = v.split("?sslmode=")[0]
        if "&sslmode=" in v:
            v = v.replace("&sslmode=require", "").replace("&sslmode=prefer", "")
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


settings = Settings()
