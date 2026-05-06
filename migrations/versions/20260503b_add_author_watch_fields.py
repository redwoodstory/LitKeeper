"""add watch_enabled, last_watch_check_at, known_story_urls to authors

Revision ID: 20260503b
Revises: 20260503a
Create Date: 2026-05-03 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260503b'
down_revision = '20260503a'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('authors')}

    with op.batch_alter_table('authors', schema=None) as batch_op:
        if 'watch_enabled' not in existing_columns:
            batch_op.add_column(sa.Column('watch_enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')))
        if 'last_watch_check_at' not in existing_columns:
            batch_op.add_column(sa.Column('last_watch_check_at', sa.DateTime(), nullable=True))
        if 'known_story_urls' not in existing_columns:
            batch_op.add_column(sa.Column('known_story_urls', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('authors', schema=None) as batch_op:
        batch_op.drop_column('known_story_urls')
        batch_op.drop_column('last_watch_check_at')
        batch_op.drop_column('watch_enabled')
