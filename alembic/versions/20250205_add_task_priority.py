"""add task priority (OBSOLETE - priority is now in initial migration)

Revision ID: 20250205_priority
Revises: 20250201_initial
Create Date: 2025-02-05

NOTE: This migration is now empty because the priority column
was added to the initial migration. Kept for migration chain integrity.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250205_priority"
down_revision = "20250201_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Priority column is already created in initial migration (20250201_initial)
    # This migration is kept for chain integrity
    pass


def downgrade() -> None:
    # Nothing to downgrade
    pass
