"""add whatsapp_number and is_active to users

Revision ID: 0003_add_whatsapp_is_active
Revises: 0002_add_admin_role
Create Date: 2026-10-21 16:48:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_add_whatsapp_is_active'
down_revision = '0002_add_admin_role'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('whatsapp_number', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False))

    # Backfill whatsapp_number from phone where possible:
    # 1. Normalize 10-digit Sri Lankan numbers starting with 0 to E.164 (+94...)
    op.execute(
        "UPDATE users SET whatsapp_number = REGEXP_REPLACE(REGEXP_REPLACE(phone, '[\\s\\-\\(\\)\\.]', '', 'g'), '^0', '+94') "
        "WHERE phone IS NOT NULL AND phone != '' AND REGEXP_REPLACE(phone, '[\\s\\-\\(\\)\\.]', '', 'g') ~ '^0[1-9][0-9]{8}$'"
    )
    # 2. Backfill any remaining non-empty phone directly
    op.execute(
        "UPDATE users SET whatsapp_number = phone "
        "WHERE phone IS NOT NULL AND phone != '' AND (whatsapp_number IS NULL OR whatsapp_number = '')"
    )


def downgrade():
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'whatsapp_number')
