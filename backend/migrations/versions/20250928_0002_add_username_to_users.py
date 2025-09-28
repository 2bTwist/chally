from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20250928_0002"
down_revision = "20250928_0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=32), nullable=True))
    conn = op.get_bind()
    # Backfill: username = normalized localpart + '_' + first 8 of id to ensure uniqueness
    conn.execute(sa.text("""
        UPDATE users
        SET username = lower(
              regexp_replace(split_part(email, '@', 1), '[^a-z0-9_]', '_', 'g')
            ) || '_' || substr(id::text, 1, 8)
        WHERE username IS NULL
    """))
    op.alter_column("users", "username", nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
