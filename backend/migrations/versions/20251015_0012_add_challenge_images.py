"""add_challenge_images

Revision ID: 20251015_0012
Revises: 20251002_0011
Create Date: 2025-10-15 07:42:42.274875

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251015_0012'
down_revision = '20251002_0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add image fields to challenges table
    op.add_column('challenges', sa.Column('image_storage_key', sa.String(length=255), nullable=True))
    op.add_column('challenges', sa.Column('image_mime_type', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # Remove image fields from challenges table
    op.drop_column('challenges', 'image_mime_type')
    op.drop_column('challenges', 'image_storage_key')