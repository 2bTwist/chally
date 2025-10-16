"""add_multi_photo_progress

Revision ID: 20251016_0015
Revises: 20251016_0014
Create Date: 2025-01-16 00:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251016_0015'
down_revision = '20251016_0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for multi-photo progress tracking
    op.add_column('submissions', sa.Column('photos_uploaded', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('submissions', sa.Column('photos_required', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('submissions', sa.Column('last_photo_uploaded_at', sa.DateTime(timezone=True), nullable=True))
    
    # Remove server defaults after backfilling
    op.alter_column('submissions', 'photos_uploaded', server_default=None)
    op.alter_column('submissions', 'photos_required', server_default=None)


def downgrade() -> None:
    op.drop_column('submissions', 'last_photo_uploaded_at')
    op.drop_column('submissions', 'photos_required')
    op.drop_column('submissions', 'photos_uploaded')
