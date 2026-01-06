"""add download queue table

Revision ID: add_download_queue
Revises: e5471813f87f
Create Date: 2026-01-06 10:53:27

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_download_queue'
down_revision = 'e5471813f87f'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'download_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(length=512), nullable=False),
        sa.Column('formats', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('story_id', sa.Integer(), nullable=True),
        sa.Column('progress_message', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['story_id'], ['stories.id'], ondelete='SET NULL')
    )

    with op.batch_alter_table('download_queue', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_download_queue_url'), ['url'], unique=False)
        batch_op.create_index(batch_op.f('ix_download_queue_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_download_queue_story_id'), ['story_id'], unique=False)

def downgrade():
    op.drop_table('download_queue')
