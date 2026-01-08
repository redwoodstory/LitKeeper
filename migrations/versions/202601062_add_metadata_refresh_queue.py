"""add metadata refresh queue

Revision ID: 202601062
Revises: 0155d9548515
Create Date: 2026-01-06 22:51:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '202601062'
down_revision = '0155d9548515'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'metadata_refresh_queue' not in inspector.get_table_names():
        op.create_table(
            'metadata_refresh_queue',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('story_id', sa.Integer(), nullable=False),
            sa.Column('url', sa.String(length=512), nullable=False),
            sa.Column('method', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('progress_message', sa.String(length=255), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=True),
            sa.Column('max_retries', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['story_id'], ['stories.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        
        with op.batch_alter_table('metadata_refresh_queue', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_metadata_refresh_queue_status'), ['status'], unique=False)
            batch_op.create_index(batch_op.f('ix_metadata_refresh_queue_story_id'), ['story_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_metadata_refresh_queue_story_id'), table_name='metadata_refresh_queue')
    op.drop_index(op.f('ix_metadata_refresh_queue_status'), table_name='metadata_refresh_queue')
    op.drop_table('metadata_refresh_queue')
