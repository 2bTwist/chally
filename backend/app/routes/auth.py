from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, UserPublic, TokenPair
from app.security import hash_password, verify_password, make_access_token, make_refresh_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", status_code=201, response_model=UserPublic)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_session)):
    exists = await session.scalar(select(User).where(User.email == payload.email))
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserPublic(id=user.id, email=user.email, created_at=user.created_at)

@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    user = await session.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenPair(access=make_access_token(str(user.id)), refresh=make_refresh_token(str(user.id)))

@router.post("/refresh", response_model=TokenPair)
async def refresh(authorization: str | None = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing refresh token")
    token = authorization.split(" ", 1)[1]
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Wrong token type")
    sub = data.get("sub")
    return TokenPair(access=make_access_token(sub), refresh=make_refresh_token(sub))

@router.get("/me", response_model=UserPublic)
async def me(authorization: str | None = Header(None), session: AsyncSession = Depends(get_session)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing access token")
    token = authorization.split(" ", 1)[1]
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if data.get("type") != "access":
        raise HTTPException(status_code=401, detail="Wrong token type")
    user_id = data.get("sub")
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return UserPublic(id=user.id, email=user.email, created_at=user.created_at)
