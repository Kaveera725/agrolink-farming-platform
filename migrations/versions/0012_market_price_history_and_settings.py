"""market price history and platform settings

Revision ID: 0012_price_history_and_settings
Revises: 0011_verification_reports
"""
from alembic import op
import sqlalchemy as sa

revision = '0012_price_history_and_settings'
down_revision = '0011_verification_reports'
branch_labels = None
depends_on = None


def upgrade():
    # 1. market_price_history table
    op.create_table(
        'market_price_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('market_price_id', sa.Integer(), sa.ForeignKey('market_prices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('old_buying', sa.Float(), nullable=True),
        sa.Column('old_selling', sa.Float(), nullable=True),
        sa.Column('new_buying', sa.Float(), nullable=False),
        sa.Column('new_selling', sa.Float(), nullable=False),
        sa.Column('changed_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('source', sa.String(length=20), nullable=False, server_default=sa.text("'manual'")),
    )
    op.create_index('ix_market_price_history_price_id', 'market_price_history', ['market_price_id'])
    op.create_index('ix_market_price_history_changed_at', 'market_price_history', ['changed_at'])

    # 2. platform_settings table
    op.create_table(
        'platform_settings',
        sa.Column('key', sa.String(length=100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('value_type', sa.String(length=20), nullable=False, server_default=sa.text("'str'")),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('platform_settings')
    op.drop_index('ix_market_price_history_changed_at', table_name='market_price_history')
    op.drop_index('ix_market_price_history_price_id', table_name='market_price_history')
    op.drop_table('market_price_history')

