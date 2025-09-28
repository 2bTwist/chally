from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime

class TokenPair(BaseModel):
    access: str
    refresh: str
