from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base

class WalletEntry(Base):
    """
    Global wallet (per user) for fiat <-> token bridging.
    Sign convention:
      - DEPOSIT   => +amount (credit user, from Stripe)
      - WITHDRAW  => -amount (cashout to Stripe/bank) [future]
      - ADJUST    => +/- (admin fix)
    Idempotency: external_id is unique (e.g., Stripe payment_intent id).
    """
    __tablename__ = "wallet_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    type: Mapped[str] = mapped_column(String(16), nullable=False)   # DEPOSIT | WITHDRAW | ADJUST
    amount: Mapped[int] = mapped_column(Integer, nullable=False)    # tokens (integer)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")  # for bookkeeping

    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)  # e.g. pi_..., cs_...
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("external_id", name="uq_wallet_external_id"),
    )