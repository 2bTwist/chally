"""Add wallet allocations and refunds tables with sign constraints

Revision ID: 20251002_0010
Revises: 20251001_0009
Create Date: 2025-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20251002_0010"
down_revision = "20251001_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add wallet allocations, refunds, and sign constraints."""
    
    # Sign check: DEPOSIT > 0, WITHDRAW < 0, ADJUST any
    op.execute("""
        ALTER TABLE wallet_entries
        ADD CONSTRAINT ck_wallet_amount_sign
        CHECK (
          (type = 'DEPOSIT' AND amount > 0) OR
          (type = 'WITHDRAW' AND amount < 0) OR
          (type = 'ADJUST')
        )
    """)

    # Allocation table: how each WITHDRAW consumed earlier DEPOSITs (FIFO)
    op.create_table(
        "wallet_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("withdraw_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wallet_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deposit_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wallet_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("tokens > 0", name="ck_wallet_alloc_tokens_pos"),
    )
    op.create_index("ix_wallet_alloc_user", "wallet_allocations", ["user_id"])
    op.create_index("ix_wallet_alloc_withdraw", "wallet_allocations", ["withdraw_entry_id"])
    op.create_index("ix_wallet_alloc_deposit", "wallet_allocations", ["deposit_entry_id"])

    # Refund audit table (one row per Stripe refund object)
    op.create_table(
        "wallet_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stripe_refund_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="usd"),
        sa.Column("status", sa.String(length=16), nullable=False),  # requested|succeeded|failed
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_wallet_refunds_user", "wallet_refunds", ["user_id"])


def downgrade() -> None:
    """Remove wallet allocations, refunds, and sign constraints."""
    op.drop_index("ix_wallet_refunds_user", table_name="wallet_refunds")
    op.drop_table("wallet_refunds")
    op.drop_index("ix_wallet_alloc_deposit", table_name="wallet_allocations")
    op.drop_index("ix_wallet_alloc_withdraw", table_name="wallet_allocations")
    op.drop_index("ix_wallet_alloc_user", table_name="wallet_allocations")
    op.drop_table("wallet_allocations")
    op.execute("ALTER TABLE wallet_entries DROP CONSTRAINT IF EXISTS ck_wallet_amount_sign")