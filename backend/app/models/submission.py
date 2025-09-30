from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db import Base


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), index=True, nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), index=True, nullable=False
    )

    slot_key: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g., '2025-01-10' local anchor date
    window_start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    proof_type: Mapped[str] = mapped_column(String(32), nullable=False)     # 'selfie' | 'env_photo' | 'text' | 'timer_screenshot'
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="accepted")  # 'pending'|'accepted'|'rejected'|'flagged'

    text_content: Mapped[str | None] = mapped_column(Text(), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("participant_id", "slot_key", name="uq_submission_one_per_slot"),
    )