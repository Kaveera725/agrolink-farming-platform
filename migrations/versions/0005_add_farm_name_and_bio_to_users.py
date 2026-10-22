"""add farm_name and bio to users

Revision ID: 0005_add_farm_name_and_bio
Revises: 0004_add_is_deleted_products
Create Date: 2026-10-22 11:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005_add_farm_name_and_bio'
down_revision = '0004_add_is_deleted_products'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('farm_name', sa.String(length=120), nullable=True))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('users', 'bio')
    op.drop_column('users', 'farm_name')
