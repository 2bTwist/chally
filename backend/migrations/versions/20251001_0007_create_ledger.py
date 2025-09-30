from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20251001_0007"
down_revision = "20250930_0006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("ref_submission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ledger_challenge_id", "ledger", ["challenge_id"])
    op.create_index("ix_ledger_participant_id", "ledger", ["participant_id"])
    op.create_index("ix_ledger_ref_submission_id", "ledger", ["ref_submission_id"])
    op.create_unique_constraint("uq_ledger_unique_ref", "ledger", ["participant_id", "type", "ref_submission_id"])

def downgrade() -> None:
    op.drop_constraint("uq_ledger_unique_ref", "ledger", type_="unique")
    op.drop_index("ix_ledger_ref_submission_id", table_name="ledger")
    op.drop_index("ix_ledger_participant_id", table_name="ledger")
    op.drop_index("ix_ledger_challenge_id", table_name="ledger")
    op.drop_table("ledger")