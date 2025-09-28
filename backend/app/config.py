from __future__ import annotations
import os
from pydantic import BaseModel

class Settings(BaseModel):
    environment: str = os.getenv("ENVIRONMENT", "development")
    app_name: str = os.getenv("APP_NAME", "peerpush-api")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    git_sha: str = os.getenv("GIT_SHA", "dev")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/peerpush_dev")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    s3_endpoint: str = os.getenv("S3_ENDPOINT", "http://minio:9000")
    s3_access_key: str = os.getenv("S3_ACCESS_KEY", "minioadmin")
    s3_secret_key: str = os.getenv("S3_SECRET_KEY", "minioadmin")
    s3_bucket_uploads: str = os.getenv("S3_BUCKET_UPLOADS", "peerpush-uploads-dev")

settings = Settings()