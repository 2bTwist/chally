from __future__ import annotations
from pydantic import BaseModel, Field, AnyHttpUrl
from uuid import UUID
from datetime import datetime

class WalletEntryPublic(BaseModel):
    id: UUID
    type: str
    amount: int
    currency: str
    external_id: str | None = None
    note: str | None = None
    created_at: datetime

class WalletSnapshot(BaseModel):
    balance: int
    entries: list[WalletEntryPublic]

class CreateDepositRequest(BaseModel):
    tokens: int = Field(gt=0, description="Number of tokens to buy")
    success_url: AnyHttpUrl
    cancel_url: AnyHttpUrl

class CreateDepositResponse(BaseModel):
    checkout_url: str
    session_id: str