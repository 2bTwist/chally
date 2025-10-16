"""add submission stages and multi photo support

Revision ID: 20251016_0013
Revises: 20251015_0012
Create Date: 2025-10-16 07:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251016_0013'
down_revision = '20251015_0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to submissions table
    op.add_column('submissions', sa.Column('submission_sequence', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('submissions', sa.Column('submission_stage', sa.String(length=32), nullable=True))
    op.add_column('submissions', sa.Column('storage_keys', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'))
    op.add_column('submissions', sa.Column('mime_types', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'))
    
    # Drop the old unique constraint that enforced one submission per slot
    op.drop_constraint('uq_submission_one_per_slot', 'submissions', type_='unique')
    
    # Create index for better query performance on participant_id and slot_key
    op.create_index('ix_submission_participant_slot', 'submissions', ['participant_id', 'slot_key'], unique=False)
    
    # Migrate existing data: populate storage_keys and mime_types arrays from single fields
    op.execute("""
        UPDATE submissions 
        SET storage_keys = CASE 
            WHEN storage_key IS NOT NULL THEN jsonb_build_array(storage_key)
            ELSE '[]'::jsonb
        END,
        mime_types = CASE 
            WHEN mime_type IS NOT NULL THEN jsonb_build_array(mime_type)
            ELSE '[]'::jsonb
        END
        WHERE storage_key IS NOT NULL OR mime_type IS NOT NULL
    """)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_submission_participant_slot', table_name='submissions')
    
    # Recreate the old unique constraint
    op.create_unique_constraint('uq_submission_one_per_slot', 'submissions', ['participant_id', 'slot_key'])
    
    # Drop new columns
    op.drop_column('submissions', 'mime_types')
    op.drop_column('submissions', 'storage_keys')
    op.drop_column('submissions', 'submission_stage')
    op.drop_column('submissions', 'submission_sequence')
