"""Enable pgcrypto extension for gen_random_uuid()

Revision ID: 20251001_0009
Revises: 20251001_0008
Create Date: 2025-10-01 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20251001_0009"
down_revision = "20251001_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable pgcrypto extension for gen_random_uuid() function."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    """Remove pgcrypto extension."""
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")