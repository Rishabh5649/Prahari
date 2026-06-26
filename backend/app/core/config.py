"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Reads all configuration from environment variables / .env file."""

    DATABASE_URL: str = "postgresql+asyncpg://prahari:prahari@localhost:5432/prahari"
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "prahari-evidence"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
