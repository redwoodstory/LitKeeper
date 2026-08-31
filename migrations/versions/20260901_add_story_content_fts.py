"""add story_content_fts full-text index

Revision ID: 20260901
Revises: 20260810
Create Date: 2026-09-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = '20260901'
down_revision = '20260810'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS story_content_fts USING fts5(
            story_id UNINDEXED,
            title,
            author,
            tags,
            body,
            tokenize = 'porter unicode61 remove_diacritics 2'
        )
        """
    )

    existing_columns = {col['name'] for col in sa.inspect(conn).get_columns('stories')}
    if 'content_indexed_at' not in existing_columns:
        with op.batch_alter_table('stories') as batch_op:
            batch_op.add_column(sa.Column('content_indexed_at', sa.DateTime(), nullable=True))
            batch_op.create_index('ix_stories_content_indexed_at', ['content_indexed_at'])


def downgrade():
    op.execute("DROP TABLE IF EXISTS story_content_fts")
    try:
        with op.batch_alter_table('stories') as batch_op:
            batch_op.drop_index('ix_stories_content_indexed_at')
            batch_op.drop_column('content_indexed_at')
    except Exception:
        pass
