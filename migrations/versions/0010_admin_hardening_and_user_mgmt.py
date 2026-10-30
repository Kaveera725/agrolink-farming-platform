"""admin hardening and user management

Revision ID: 0010_admin_hardening
Revises: 0009_add_admin_audit_log
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0010_admin_hardening'
down_revision = '0009_add_admin_audit_log'
branch_labels = None
depends_on = None


def upgrade():
    # 1. users table updates
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('session_version', sa.Integer(), nullable=False, server_default=sa.text('1')))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))

    # 2. products table updates
    op.add_column('products', sa.Column('hidden_reason', sa.String(length=30), nullable=True))
    op.add_column('products', sa.Column('hidden_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))

    # 3. admin_audit_log table updates
    op.add_column('admin_audit_log', sa.Column('ip_address', sa.String(length=45), nullable=True))
    op.add_column('admin_audit_log', sa.Column('user_agent', sa.String(length=255), nullable=True))
    op.add_column('admin_audit_log', sa.Column('before_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('admin_audit_log', sa.Column('after_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('admin_audit_log', sa.Column('result', sa.String(length=20), nullable=False, server_default=sa.text("'success'")))
    op.alter_column('admin_audit_log', 'admin_id', nullable=True)

    # 4. admin_notes table
    op.create_table(
        'admin_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('admin_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_admin_notes_user_id', 'admin_notes', ['user_id'])

    # 5. PostgreSQL append-only trigger for admin_audit_log
    op.execute("""
    CREATE OR REPLACE FUNCTION prevent_admin_audit_log_modification()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'admin_audit_log is append-only: UPDATE and DELETE are prohibited.';
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    DROP TRIGGER IF EXISTS trg_prevent_admin_audit_log_modification ON admin_audit_log;
    CREATE TRIGGER trg_prevent_admin_audit_log_modification
    BEFORE UPDATE OR DELETE ON admin_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_admin_audit_log_modification();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_admin_audit_log_modification ON admin_audit_log;")
    op.execute("DROP FUNCTION IF EXISTS prevent_admin_audit_log_modification();")

    op.drop_index('ix_admin_notes_user_id', table_name='admin_notes')
    op.drop_table('admin_notes')

    op.alter_column('admin_audit_log', 'admin_id', nullable=False)
    op.drop_column('admin_audit_log', 'result')
    op.drop_column('admin_audit_log', 'after_data')
    op.drop_column('admin_audit_log', 'before_data')
    op.drop_column('admin_audit_log', 'user_agent')
    op.drop_column('admin_audit_log', 'ip_address')

    op.drop_column('products', 'hidden_by')
    op.drop_column('products', 'hidden_reason')

    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'session_version')
    op.drop_column('users', 'must_change_password')

