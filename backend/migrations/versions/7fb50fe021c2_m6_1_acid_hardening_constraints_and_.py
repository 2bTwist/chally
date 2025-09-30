"""M6.1 ACID hardening - constraints and indexes

Revision ID: 7fb50fe021c2
Revises: 20251001_0007
Create Date: 2025-09-30 10:04:49.291467

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7fb50fe021c2'
down_revision = '20251001_0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add CHECK constraint to ensure amount signs match transaction types
    op.execute("""
        ALTER TABLE ledger
        ADD CONSTRAINT ck_ledger_amount_sign
        CHECK (
            (type IN ('STAKE','PENALTY') AND amount < 0) OR
            (type = 'PAYOUT' AND amount > 0)
        )
    """)
    
    # Add unique index to guarantee only one stake per participant
    op.execute("""
        CREATE UNIQUE INDEX uq_ledger_stake_once
        ON ledger (participant_id) WHERE type = 'STAKE'
    """)


def downgrade() -> None:
    # Remove the unique index
    op.execute("DROP INDEX IF EXISTS uq_ledger_stake_once")
    
    # Remove the CHECK constraint
    op.execute("ALTER TABLE ledger DROP CONSTRAINT IF EXISTS ck_ledger_amount_sign")