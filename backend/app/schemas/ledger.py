from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class LedgerEntryPublic(BaseModel):
    id: UUID
    challenge_id: UUID
    participant_id: UUID
    type: str
    amount: int
    ref_submission_id: UUID | None = None
    note: str | None = None
    created_at: datetime

class ParticipantBalance(BaseModel):
    participant_id: UUID
    user_id: UUID
    username: str
    balance: int

class LedgerSnapshot(BaseModel):
    challenge_id: UUID
    pool_tokens: int
    your_balance: int
    totals: list[ParticipantBalance]
    entries: list[LedgerEntryPublic]