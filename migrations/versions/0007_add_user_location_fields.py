"""add latitude longitude address_text location_updated_at to users

Revision ID: 0007_add_user_location_fields
Revises: 0006_add_profile_image_url
Create Date: 2026-10-25 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0007_add_user_location_fields'
down_revision = '0006_add_profile_image_url'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('users', sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('users', sa.Column('address_text', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('location_updated_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'location_updated_at')
    op.drop_column('users', 'address_text')
    op.drop_column('users', 'longitude')
    op.drop_column('users', 'latitude')
