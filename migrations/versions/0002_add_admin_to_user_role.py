"""add admin to user_role enum

Revision ID: 0002_add_admin_role
Revises: 0001_baseline
Create Date: 2026-10-21 16:47:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_admin_role'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'admin'")


def downgrade():
    # PostgreSQL does not allow easily dropping values from an existing enum type without table rewrite
    pass
