"""add unique constraint to metadata refresh queue

Revision ID: 202601071
Revises: 202601062
Create Date: 2026-01-07 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '202601071'
down_revision = '202601062'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes('metadata_refresh_queue')]
    
    if 'ix_metadata_refresh_queue_story_active' not in indexes:
        if conn.dialect.name == 'sqlite':
            with op.batch_alter_table('metadata_refresh_queue', schema=None) as batch_op:
                batch_op.create_index(
                    'ix_metadata_refresh_queue_story_active',
                    ['story_id', 'status'],
                    unique=False
                )
        else:
            op.create_index(
                'ix_metadata_refresh_queue_story_active',
                'metadata_refresh_queue',
                ['story_id', 'status'],
                unique=False,
                postgresql_where=sa.text("status IN ('pending', 'processing')")
            )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes('metadata_refresh_queue')]
    
    if 'ix_metadata_refresh_queue_story_active' in indexes:
        op.drop_index('ix_metadata_refresh_queue_story_active', table_name='metadata_refresh_queue')
