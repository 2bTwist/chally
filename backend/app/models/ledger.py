from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base

class Ledger(Base):
    """
    Event-sourced entries per participant.
    Sign convention:
      - STAKE   => negative (debit user into pool)
      - PENALTY => negative (debit user into pool)
      - PAYOUT  => positive (credit user from pool)

    Pool = sum of (-amounts) currently in the challenge.
    After payout, Σ(amount) per challenge = 0.
    """
    __tablename__ = "ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("challenges.id", ondelete="CASCADE"), index=True, nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), index=True, nullable=False
    )

    type: Mapped[str] = mapped_column(String(16), nullable=False)  # STAKE | PENALTY | PAYOUT
    amount: Mapped[int] = mapped_column(Integer, nullable=False)   # sign as per convention

    # For idempotency on penalties (1 per submission)
    ref_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # Allows only one (participant, type, submission) penalty per submission, and harmless for stake/payout (ref null)
        UniqueConstraint("participant_id", "type", "ref_submission_id", name="uq_ledger_unique_ref"),
    )