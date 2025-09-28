from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "15"))
REFRESH_TTL_MIN = int(os.getenv("REFRESH_TTL_MIN", "10080"))  # 7d

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def _make_token(sub: str, ttl_min: int, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": token_type,
        "iat": now.timestamp(),  # Use float for microsecond precision
        "exp": int((now + timedelta(minutes=ttl_min)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def make_access_token(sub: str) -> str:
    return _make_token(sub, ACCESS_TTL_MIN, "access")

def make_refresh_token(sub: str) -> str:
    return _make_token(sub, REFRESH_TTL_MIN, "refresh")

def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
