"""add queue and opened timestamps

Revision ID: 20260326b
Revises: 20260326
Create Date: 2026-03-26 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260326b'
down_revision = '0155d9548515'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('stories')}
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('stories')}

    if 'queued_at' not in existing_columns:
        op.add_column('stories', sa.Column('queued_at', sa.DateTime(), nullable=True))
    if 'ix_stories_queued_at' not in existing_indexes:
        op.create_index(op.f('ix_stories_queued_at'), 'stories', ['queued_at'], unique=False)

    if 'last_opened_at' not in existing_columns:
        op.add_column('stories', sa.Column('last_opened_at', sa.DateTime(), nullable=True))
    if 'ix_stories_last_opened_at' not in existing_indexes:
        op.create_index(op.f('ix_stories_last_opened_at'), 'stories', ['last_opened_at'], unique=False)


def downgrade():
    # Remove indexes and columns
    op.drop_index(op.f('ix_stories_last_opened_at'), table_name='stories')
    op.drop_column('stories', 'last_opened_at')
    
    op.drop_index(op.f('ix_stories_queued_at'), table_name='stories')
    op.drop_column('stories', 'queued_at')
