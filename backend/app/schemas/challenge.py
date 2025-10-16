from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, ConfigDict, field_serializer
from typing import Literal, List
from uuid import UUID
from datetime import datetime, time

ProofType = Literal["selfie", "env_photo", "text", "timer_screenshot"]
Frequency = Literal["daily", "weekly", "weekdays", "custom"]
VerificationMode = Literal["auto", "quorum"]
Visibility = Literal["public", "private", "code"]
ChallengeStatus = Literal["draft", "active", "canceled", "deleted"]
RuntimeState = Literal["upcoming", "started", "ended", "canceled", "deleted"]

class TimeWindow(BaseModel):
    model_config = ConfigDict()

    @field_serializer("start", "end")
    def serialize_time(self, value: time) -> str:
        return value.strftime('%H:%M:%S')

    start: time
    end: time
    timezone: str | None = None  # used when scope = "challenge_tz"
    scope: Literal["participant_local", "challenge_tz"] = "participant_local"

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
    
    # Anti-cheat settings
    anti_cheat_overlay_required: bool = True
    anti_cheat_exif_required: bool = True
    anti_cheat_phash_check: bool = True
    
    # NEW: Submission limits and intervals
    max_submissions_per_slot: int = Field(ge=1, default=1, description="How many submissions allowed per day/week")
    submission_interval_minutes: int | None = Field(default=None, ge=0, description="Minimum minutes between submissions")
    
    # NEW: Submission stages (optional structured workflow)
    require_submission_stages: bool = Field(default=False, description="If true, must submit in order")
    submission_stages: List[str] | None = Field(default=None, description="e.g., ['start', 'ongoing', 'end']")
    
    # NEW: Custom days (for frequency="custom")
    custom_days: List[int] | None = Field(default=None, description="Weekday integers: 0=Monday, 6=Sunday")
    
    # NEW: Multi-photo support
    photos_per_submission: int = Field(ge=1, default=1, description="How many photos required per submission")

    @field_validator("proof_types")
    @classmethod
    def non_empty(cls, v: list[str]):
        if not v:
            raise ValueError("proof_types must not be empty")
        return v
    
    @field_validator("custom_days")
    @classmethod
    def validate_custom_days(cls, v: List[int] | None):
        if v is not None:
            for day in v:
                if day < 0 or day > 6:
                    raise ValueError("custom_days must be integers between 0 (Monday) and 6 (Sunday)")
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
    status: ChallengeStatus
    created_at: datetime
    # New fields:
    participant_count: int
    is_owner: bool
    is_participant: bool
    runtime_state: RuntimeState
    # Challenge image fields
    image_url: str | None = None  # presigned URL for challenge image
    has_image: bool = False  # whether challenge has an image

class ParticipantPublic(BaseModel):
    id: UUID
    challenge_id: UUID
    user_id: UUID
    joined_at: datetime
    timezone: str

class ParticipantWithUser(BaseModel):
    participant_id: UUID
    user_id: UUID
    username: str
    joined_at: datetime