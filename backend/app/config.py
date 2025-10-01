from __future__ import annotations
import os
from pydantic import BaseModel

class Settings(BaseModel):
    environment: str = os.getenv("ENVIRONMENT", "dev")
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
    # Media exposure controls
    serve_media_via_api: bool = os.getenv("SERVE_MEDIA_VIA_API", "1") == "1"
    s3_presign_downloads: bool = os.getenv("S3_PRESIGN_DOWNLOADS", "0") == "1"
    s3_presign_expiry_seconds: int = int(os.getenv("S3_PRESIGN_EXPIRY_SECONDS", "300"))
    
    # Stripe configuration
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    token_price_usd_cents: int = int(os.getenv("TOKEN_PRICE_USD_CENTS", "1"))
    
    # Withdrawal configuration
    withdraw_mode: str = os.getenv("WITHDRAW_MODE", "refund")  # refund|disabled (Connect later)
    max_deposit_tokens_day: int = int(os.getenv("MAX_DEPOSIT_TOKENS_DAY", "100000"))  # e.g. $1,000 if 1 token = 1 cent
    refund_window_days: int = int(os.getenv("REFUND_WINDOW_DAYS", "90"))  # typical 90d

settings = Settings()