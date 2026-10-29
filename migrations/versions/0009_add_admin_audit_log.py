"""add admin audit log

Revision ID: 0009_add_admin_audit_log
Revises: 0008_add_delivery_pricing_fields
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_add_admin_audit_log'
down_revision = '0008_add_delivery_pricing_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'admin_audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('admin_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(length=80), nullable=False),
        sa.Column('target_type', sa.String(length=40), nullable=True),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_admin_audit_log_created_at', 'admin_audit_log', ['created_at'])


def downgrade():
    op.drop_index('ix_admin_audit_log_created_at', table_name='admin_audit_log')
    op.drop_table('admin_audit_log')