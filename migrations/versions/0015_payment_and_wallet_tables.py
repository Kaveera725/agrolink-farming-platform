"""add payment, order payment_status, and wallet tables and fields

Revision ID: 0015_payment_and_wallet_tables
Revises: 0014_data_requests
Create Date: 2026-11-12 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0015_payment_and_wallet_tables'
down_revision = '0014_data_requests'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create Enums if they do not exist
    op.execute("DO $$ BEGIN CREATE TYPE order_payment_status AS ENUM ('unpaid', 'pending', 'paid', 'failed', 'refunded'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE payment_status AS ENUM ('initiated', 'success', 'failed', 'expired', 'refunded'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE wallet_transaction_type AS ENUM ('credit', 'reversal'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    order_payment_status_type = postgresql.ENUM('unpaid', 'pending', 'paid', 'failed', 'refunded', name='order_payment_status', create_type=False)
    payment_status_type = postgresql.ENUM('initiated', 'success', 'failed', 'expired', 'refunded', name='payment_status', create_type=False)
    wallet_transaction_type_type = postgresql.ENUM('credit', 'reversal', name='wallet_transaction_type', create_type=False)

    # 2. Add wallet_balance to users
    op.add_column('users', sa.Column('wallet_balance', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))

    # 3. Add payment_status to orders and backfill legacy orders
    op.add_column('orders', sa.Column('payment_status', order_payment_status_type, server_default='unpaid', nullable=False))
    op.execute("UPDATE orders SET payment_status = 'unpaid' WHERE payment_status IS NULL")

    # 4. Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('method', sa.String(length=20), server_default='card', nullable=False),
        sa.Column('status', payment_status_type, server_default='initiated', nullable=False),
        sa.Column('txn_ref', sa.String(length=40), nullable=False),
        sa.Column('failure_reason', sa.String(length=255), nullable=True),
        sa.Column('card_brand', sa.String(length=20), nullable=True),
        sa.Column('card_last4', sa.String(length=4), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('txn_ref', name='uq_payments_txn_ref')
    )
    op.create_index('ix_payments_order_id_status', 'payments', ['order_id', 'status'])
    op.create_index('ix_payments_txn_ref', 'payments', ['txn_ref'])

    # 5. Create wallet_transactions table
    op.create_table(
        'wallet_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True),
        sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('type', wallet_transaction_type_type, nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('balance_after', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('ix_wallet_transactions_user_id', 'wallet_transactions', ['user_id'])


def downgrade():
    op.drop_index('ix_wallet_transactions_user_id', table_name='wallet_transactions')
    op.drop_table('wallet_transactions')

    op.drop_index('ix_payments_txn_ref', table_name='payments')
    op.drop_index('ix_payments_order_id_status', table_name='payments')
    op.drop_table('payments')

    op.drop_column('orders', 'payment_status')
    op.drop_column('users', 'wallet_balance')

    wallet_transaction_type_enum = postgresql.ENUM('credit', 'reversal', name='wallet_transaction_type')
    wallet_transaction_type_enum.drop(op.get_bind(), checkfirst=True)

    payment_status_enum = postgresql.ENUM('initiated', 'success', 'failed', 'expired', 'refunded', name='payment_status')
    payment_status_enum.drop(op.get_bind(), checkfirst=True)

    order_payment_status_enum = postgresql.ENUM('unpaid', 'pending', 'paid', 'failed', 'refunded', name='order_payment_status')
    order_payment_status_enum.drop(op.get_bind(), checkfirst=True)

