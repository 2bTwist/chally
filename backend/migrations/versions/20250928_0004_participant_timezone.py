"""participant timezone

Revision ID: 20250928_0004
Revises: 20250928_0003
Create Date: 2025-09-28 22:10:00.000000

"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250928_0004"
down_revision = "20250928_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add timezone column as nullable first
    op.add_column("participants", sa.Column("timezone", sa.String(length=64), nullable=True))
    
    # Set default timezone for existing records
    op.execute("UPDATE participants SET timezone = 'UTC' WHERE timezone IS NULL")
    
    # Make column NOT NULL after setting defaults
    op.alter_column("participants", "timezone", nullable=False)


def downgrade() -> None:
    op.drop_column("participants", "timezone")