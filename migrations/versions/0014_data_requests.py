"""add data_requests table for pdpa 2022 privacy tools

Revision ID: 0014_data_requests
Revises: 0013_dashboard_reporting_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = '0014_data_requests'
down_revision = '0013_dashboard_reporting_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'data_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'open'")),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('handled_at', sa.DateTime(), nullable=True),
        sa.Column('handled_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_data_requests_user_id', 'data_requests', ['user_id'])
    op.create_index('ix_data_requests_status', 'data_requests', ['status'])
    op.create_index('ix_data_requests_type', 'data_requests', ['type'])


def downgrade():
    op.drop_index('ix_data_requests_type', table_name='data_requests')
    op.drop_index('ix_data_requests_status', table_name='data_requests')
    op.drop_index('ix_data_requests_user_id', table_name='data_requests')
    op.drop_table('data_requests')

