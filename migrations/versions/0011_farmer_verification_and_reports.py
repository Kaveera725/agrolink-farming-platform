"""farmer verification and listing reports

Revision ID: 0011_verification_reports
Revises: 0010_admin_hardening
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_verification_reports'
down_revision = '0010_admin_hardening'
branch_labels = None
depends_on = None


def upgrade():
    # 1. users table updates for farmer verification
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('verified_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('verified_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    # 2. admin_notes table updates to support orders
    op.add_column('admin_notes', sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=True))
    op.alter_column('admin_notes', 'user_id', nullable=True)
    op.create_index('ix_admin_notes_order_id', 'admin_notes', ['order_id'])

    # 3. verification_requests table
    op.create_table(
        'verification_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('farmer_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('farmer_note', sa.Text(), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decided_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_verification_requests_farmer_id', 'verification_requests', ['farmer_id'])
    op.create_index('ix_verification_requests_status', 'verification_requests', ['status'])

    # 4. listing_reports table
    op.create_table(
        'listing_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reporter_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.String(length=50), nullable=False),
        sa.Column('details', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'open'")),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('handled_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('handled_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_listing_reports_product_id', 'listing_reports', ['product_id'])
    op.create_index('ix_listing_reports_reporter_id', 'listing_reports', ['reporter_id'])
    op.create_index('ix_listing_reports_status', 'listing_reports', ['status'])


def downgrade():
    op.drop_table('listing_reports')
    op.drop_table('verification_requests')
    op.drop_index('ix_admin_notes_order_id', table_name='admin_notes')
    op.drop_column('admin_notes', 'order_id')
    op.alter_column('admin_notes', 'user_id', nullable=False)
    op.drop_column('users', 'verified_by')
    op.drop_column('users', 'verified_at')
    op.drop_column('users', 'is_verified')

