"""add delivery pricing fields to products and orders

Revision ID: 0008_add_delivery_pricing_fields
Revises: 0007_add_user_location_fields
Create Date: 2026-10-26 23:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0008_add_delivery_pricing_fields'
down_revision = '0007_add_user_location_fields'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add 'rejected' to order_status enum if not present
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'rejected'")

    # 2. Create fulfillment_type enum
    fulfillment_type_enum = postgresql.ENUM('pickup', 'delivery', name='fulfillment_type')
    fulfillment_type_enum.create(op.get_bind(), checkfirst=True)

    # 3. Create distance_source enum
    distance_source_enum = postgresql.ENUM('google', 'estimated', name='distance_source')
    distance_source_enum.create(op.get_bind(), checkfirst=True)

    # 4. Add offers_delivery to products
    op.add_column('products', sa.Column('offers_delivery', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    # 5. Add columns to orders
    op.add_column('orders', sa.Column('fulfillment_type', sa.Enum('pickup', 'delivery', name='fulfillment_type'), server_default='pickup', nullable=False))
    op.add_column('orders', sa.Column('delivery_lat', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('orders', sa.Column('delivery_lng', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('orders', sa.Column('distance_km', sa.Numeric(precision=8, scale=2), nullable=True))
    op.add_column('orders', sa.Column('distance_source', sa.Enum('google', 'estimated', name='distance_source'), nullable=True))
    op.add_column('orders', sa.Column('items_total', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('orders', sa.Column('delivery_fee', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False))
    op.add_column('orders', sa.Column('rejection_reason', sa.String(length=255), nullable=True))

    # 6. Backfill legacy orders: fulfillment_type = 'pickup', items_total = total_price, delivery_fee = 0
    op.execute("""
        UPDATE orders
        SET fulfillment_type = 'pickup',
            items_total = total_price,
            delivery_fee = 0
        WHERE items_total IS NULL
    """)


def downgrade():
    # 1. Drop columns from orders
    op.drop_column('orders', 'rejection_reason')
    op.drop_column('orders', 'delivery_fee')
    op.drop_column('orders', 'items_total')
    op.drop_column('orders', 'distance_source')
    op.drop_column('orders', 'distance_km')
    op.drop_column('orders', 'delivery_lng')
    op.drop_column('orders', 'delivery_lat')
    op.drop_column('orders', 'fulfillment_type')

    # 2. Drop column from products
    op.drop_column('products', 'offers_delivery')

    # 3. Drop custom enums
    fulfillment_type_enum = postgresql.ENUM('pickup', 'delivery', name='fulfillment_type')
    fulfillment_type_enum.drop(op.get_bind(), checkfirst=True)

    distance_source_enum = postgresql.ENUM('google', 'estimated', name='distance_source')
    distance_source_enum.drop(op.get_bind(), checkfirst=True)

    # Note: PostgreSQL does not support easily dropping enum values ('rejected') from order_status without table rewrite
