"""add profile_image_url to users

Revision ID: 0006_add_profile_image_url
Revises: 0005_add_farm_name_and_bio
Create Date: 2026-10-22 11:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006_add_profile_image_url'
down_revision = '0005_add_farm_name_and_bio'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('profile_image_url', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('users', 'profile_image_url')
