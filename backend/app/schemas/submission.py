from __future__ import annotations
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class SubmissionPublic(BaseModel):
    id: UUID
    challenge_id: UUID
    participant_id: UUID
    slot_key: str
    window_start_utc: datetime
    window_end_utc: datetime
    submitted_at: datetime
    proof_type: str
    status: str
    text_content: str | None = None
    mime_type: str | None = None
    # 🔒 do not expose storage keys
    media_url: str | None = None   # served via proxy endpoint
    meta: dict = Field(default_factory=dict)


class FeedItem(BaseModel):
    challenge_id: UUID
    challenge_name: str
    submitted_today: bool
    my_submission: SubmissionPublic | None = None


class LeaderboardRow(BaseModel):
    user_id: UUID
    username: str
    total: int
    submitted_today: bool