from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Literal, List
from uuid import UUID
from datetime import datetime, time

ProofType = Literal["selfie", "env_photo", "text", "timer_screenshot"]
Frequency = Literal["daily", "weekly", "weekdays"]
VerificationMode = Literal["auto", "quorum"]
Visibility = Literal["public", "private", "code"]

class TimeWindow(BaseModel):
    model_config = ConfigDict(
        json_encoders={
            time: lambda v: v.strftime('%H:%M:%S')
        }
    )
    
    start: time
    end: time
    timezone: str

class Verification(BaseModel):
    mode: VerificationMode
    quorum_pct: int = Field(default=60, ge=50, le=100)

class RulesDSL(BaseModel):
    frequency: Frequency
    time_window: TimeWindow
    proof_types: List[ProofType]
    verification: Verification
    grace: int = Field(ge=0, default=0)
    penalties: int = Field(ge=0, default=0, description="per_miss_tokens")
    anti_cheat_overlay_required: bool = True
    anti_cheat_exif_required: bool = True
    anti_cheat_phash_check: bool = True

    @field_validator("proof_types")
    @classmethod
    def non_empty(cls, v: list[str]):
        if not v:
            raise ValueError("proof_types must not be empty")
        return v

class ChallengeCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str | None = None
    visibility: Visibility = "code"
    starts_at: datetime
    ends_at: datetime
    entry_stake_tokens: int = Field(ge=0, default=0)
    rules: RulesDSL

class ChallengePublic(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    visibility: Visibility
    invite_code: str
    starts_at: datetime
    ends_at: datetime
    entry_stake_tokens: int
    rules: RulesDSL
    status: str
    created_at: datetime

class ParticipantPublic(BaseModel):
    id: UUID
    challenge_id: UUID
    user_id: UUID
    joined_at: datetime