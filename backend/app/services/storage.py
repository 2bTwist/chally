from __future__ import annotations
import io
from minio import Minio
from minio.error import S3Error
from app.config import settings

def _parse_endpoint(ep: str) -> tuple[str, bool]:
    # Return (host:port, secure)
    secure = ep.startswith("https://")
    host = ep.replace("http://", "").replace("https://", "")
    return host, secure

_host, _secure = _parse_endpoint(settings.s3_endpoint)
_client = Minio(_host, access_key=settings.s3_access_key, secret_key=settings.s3_secret_key, secure=_secure)

# Ensure bucket exists (idempotent)
try:
    if not _client.bucket_exists(settings.s3_bucket_uploads):
        _client.make_bucket(settings.s3_bucket_uploads)
except S3Error:
    # In dev, bucket creation may race; it's fine if it already exists
    pass

def put_bytes(key: str, data: bytes, content_type: str) -> None:
    _client.put_object(
        settings.s3_bucket_uploads, key, io.BytesIO(data), length=len(data), content_type=content_type
    )