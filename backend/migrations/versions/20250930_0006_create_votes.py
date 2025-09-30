from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20250930_0006"
down_revision = "20250928_0005"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voter_participant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approve", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_votes_submission_id", "votes", ["submission_id"])
    op.create_index("ix_votes_voter_participant_id", "votes", ["voter_participant_id"])
    op.create_unique_constraint("uq_vote_once_per_voter", "votes", ["submission_id", "voter_participant_id"])

def downgrade() -> None:
    op.drop_constraint("uq_vote_once_per_voter", "votes", type_="unique")
    op.drop_index("ix_votes_voter_participant_id", table_name="votes")
    op.drop_index("ix_votes_submission_id", table_name="votes")
    op.drop_table("votes")