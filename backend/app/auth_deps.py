from __future__ import annotations
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.security import decode_token
from app.models.user import User

async def get_current_user(authorization: str | None = Header(None), session: AsyncSession = Depends(get_session)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing access token")
    token = authorization.split(" ", 1)[1]
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if data.get("type") != "access":
        raise HTTPException(status_code=401, detail="Wrong token type")
    user = await session.get(User, data.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user