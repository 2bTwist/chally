from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20250928_0003"
down_revision = "20250928_0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="code"),
        sa.Column("invite_code", sa.String(length=12), nullable=False),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("entry_stake_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_challenges_invite_code", "challenges", ["invite_code"], unique=True)
    op.create_index("ix_challenges_owner_id", "challenges", ["owner_id"])

    op.create_table(
        "participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_participants_challenge_id", "participants", ["challenge_id"])
    op.create_index("ix_participants_user_id", "participants", ["user_id"])
    op.create_unique_constraint("uq_participant_unique", "participants", ["challenge_id", "user_id"])

def downgrade() -> None:
    op.drop_constraint("uq_participant_unique", "participants", type_="unique")
    op.drop_index("ix_participants_user_id", table_name="participants")
    op.drop_index("ix_participants_challenge_id", table_name="participants")
    op.drop_table("participants")
    op.drop_index("ix_challenges_owner_id", table_name="challenges")
    op.drop_index("ix_challenges_invite_code", table_name="challenges")
    op.drop_table("challenges")