from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20250928_0005"
down_revision = "20250928_0004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot_key", sa.String(length=32), nullable=False),
        sa.Column("window_start_utc", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("window_end_utc", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("proof_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="accepted"),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=64), nullable=True),
        sa.Column("meta_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.UniqueConstraint("participant_id", "slot_key", name="uq_submission_one_per_slot"),
    )
    op.create_index("ix_submissions_challenge_id", "submissions", ["challenge_id"])
    op.create_index("ix_submissions_slot_key", "submissions", ["slot_key"])

def downgrade() -> None:
    op.drop_index("ix_submissions_slot_key", table_name="submissions")
    op.drop_index("ix_submissions_challenge_id", table_name="submissions")
    op.drop_table("submissions")