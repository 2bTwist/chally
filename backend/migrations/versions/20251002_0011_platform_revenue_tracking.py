"""Add platform revenue tracking for forfeited stakes

Revision ID: 20251002_0011
Revises: 20251002_0010
Create Date: 2025-10-02 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251002_0011"
down_revision = "20251002_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add platform revenue tracking capabilities."""
    
    # 1. Drop the foreign key constraint on participant_id to allow platform pseudo-participant
    op.execute("ALTER TABLE ledger DROP CONSTRAINT IF EXISTS ledger_participant_id_fkey")
    
    # 2. Expand the type column to support PLATFORM_REVENUE
    op.execute("ALTER TABLE ledger ALTER COLUMN type TYPE VARCHAR(20)")
    
    # 3. Update the amount sign constraint to allow PLATFORM_REVENUE (positive)
    op.execute("ALTER TABLE ledger DROP CONSTRAINT IF EXISTS ck_ledger_amount_sign")
    op.execute("""
        ALTER TABLE ledger
        ADD CONSTRAINT ck_ledger_amount_sign
        CHECK (
            (type IN ('STAKE','PENALTY') AND amount < 0) OR
            (type IN ('PAYOUT','PLATFORM_REVENUE') AND amount > 0)
        )
    """)
    
    # 4. Add index on participant_id since we removed the FK (which had an index) - only if not exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_ledger_participant_id ON ledger (participant_id)")


def downgrade() -> None:
    """Remove platform revenue tracking capabilities."""
    
    # 1. Remove any PLATFORM_REVENUE entries (they shouldn't exist if we're downgrading)
    op.execute("DELETE FROM ledger WHERE type = 'PLATFORM_REVENUE'")
    
    # 2. Drop the index we created (if it exists)
    op.execute("DROP INDEX IF EXISTS ix_ledger_participant_id")
    
    # 3. Restore the foreign key constraint (all participant_ids should be valid after deleting PLATFORM_REVENUE)
    op.execute("""
        ALTER TABLE ledger 
        ADD CONSTRAINT ledger_participant_id_fkey 
        FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
    """)
    
    # 4. Shrink the type column back
    op.execute("ALTER TABLE ledger ALTER COLUMN type TYPE VARCHAR(16)")