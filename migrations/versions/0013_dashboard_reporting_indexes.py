"""dashboard and reporting indexes

Revision ID: 0013_dashboard_reporting_indexes
Revises: 0012_price_history_and_settings
"""
from alembic import op
import sqlalchemy as sa

revision = '0013_dashboard_reporting_indexes'
down_revision = '0012_price_history_and_settings'
branch_labels = None
depends_on = None


def upgrade():
    # Performance indexes for dashboard aggregations and reporting
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_created_at_status ON orders (created_at, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_status ON orders (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_fulfillment_type ON orders (fulfillment_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_product_status ON orders (product_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_farmer_avail_del ON products (farmer_id, is_available, is_deleted)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_qty_avail_del ON products (quantity_kg, is_available, is_deleted)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_role_created_at ON users (role, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_location_role ON users (location, role)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_lat_lng ON users (latitude, longitude)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_users_lat_lng")
    op.execute("DROP INDEX IF EXISTS ix_users_location_role")
    op.execute("DROP INDEX IF EXISTS ix_users_role_created_at")
    op.execute("DROP INDEX IF EXISTS ix_products_qty_avail_del")
    op.execute("DROP INDEX IF EXISTS ix_products_farmer_avail_del")
    op.execute("DROP INDEX IF EXISTS ix_orders_product_status")
    op.execute("DROP INDEX IF EXISTS ix_orders_fulfillment_type")
    op.execute("DROP INDEX IF EXISTS ix_orders_status")
    op.execute("DROP INDEX IF EXISTS ix_orders_created_at_status")
