"""drop ix_metadata_refresh_queue_story_active index

NOTE: This migration was originally misnamed "add curated_stories table" by alembic
autogenerate, which failed to detect the curated_stories table (created outside Alembic)
and instead captured an unrelated index drift on metadata_refresh_queue.

Revision ID: 61fb23c819e4
Revises: 20260505a
Create Date: 2026-06-15 15:57:05.546657

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '61fb23c819e4'
down_revision = '20260505a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('metadata_refresh_queue', schema=None) as batch_op:
        batch_op.drop_index('ix_metadata_refresh_queue_story_active')


def downgrade():
    with op.batch_alter_table('metadata_refresh_queue', schema=None) as batch_op:
        batch_op.create_index('ix_metadata_refresh_queue_story_active', ['story_id', 'status'], unique=False)
