"""add is_deleted to products

Revision ID: 0004_add_is_deleted_products
Revises: 0003_add_whatsapp_is_active
Create Date: 2026-10-21 17:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_add_is_deleted_products'
down_revision = '0003_add_whatsapp_is_active'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade():
    op.drop_column('products', 'is_deleted')
