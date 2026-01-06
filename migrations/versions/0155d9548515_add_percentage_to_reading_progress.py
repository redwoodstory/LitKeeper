"""add_percentage_to_reading_progress

Revision ID: 0155d9548515
Revises: add_download_queue
Create Date: 2026-01-06 14:16:46.710642

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0155d9548515'
down_revision = 'add_download_queue'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('reading_progress', sa.Column('percentage', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('reading_progress', 'percentage')
