from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20251001_0008"
down_revision = "7fb50fe021c2"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "wallet_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="usd"),
        sa.Column("external_id", sa.String(length=64), nullable=True, unique=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_wallet_entries_user_id", "wallet_entries", ["user_id"])

def downgrade() -> None:
    op.drop_index("ix_wallet_entries_user_id", table_name="wallet_entries")
    op.drop_table("wallet_entries")