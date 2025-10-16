"""update visibility system

Revision ID: 20251016_0014
Revises: 20251016_0013
Create Date: 2025-10-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251016_0014'
down_revision = '20251016_0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update visibility enum values
    # Change 'code' to 'public' for all existing challenges
    op.execute("UPDATE challenges SET visibility = 'public' WHERE visibility = 'code'")
    
    # Ensure all challenges have an invite_code
    # Generate codes for any challenges that don't have one
    op.execute("""
        UPDATE challenges 
        SET invite_code = UPPER(SUBSTRING(MD5(RANDOM()::TEXT || id::TEXT) FROM 1 FOR 8))
        WHERE invite_code IS NULL
    """)
    
    # Ensure invite codes are unique (handle collisions)
    op.execute("""
        WITH duplicates AS (
            SELECT id, invite_code, 
                   ROW_NUMBER() OVER (PARTITION BY invite_code ORDER BY created_at) as rn
            FROM challenges
            WHERE invite_code IS NOT NULL
        )
        UPDATE challenges c
        SET invite_code = UPPER(SUBSTRING(MD5(RANDOM()::TEXT || c.id::TEXT) FROM 1 FOR 8))
        FROM duplicates d
        WHERE c.id = d.id AND d.rn > 1
    """)
    
    # Make invite_code NOT NULL and ensure it's indexed
    op.alter_column('challenges', 'invite_code', nullable=False)
    
    # Drop existing index if it exists and recreate as unique
    op.execute("DROP INDEX IF EXISTS ix_challenge_invite_code")
    op.create_index('ix_challenge_invite_code', 'challenges', ['invite_code'], unique=True)


def downgrade() -> None:
    # Revert changes
    op.drop_index('ix_challenge_invite_code', table_name='challenges')
    op.alter_column('challenges', 'invite_code', nullable=True)
    op.execute("UPDATE challenges SET visibility = 'code' WHERE visibility = 'public'")
