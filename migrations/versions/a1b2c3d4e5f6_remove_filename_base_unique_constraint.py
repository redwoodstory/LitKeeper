"""remove filename_base unique constraint

Revision ID: a1b2c3d4e5f6
Revises: f18425943940
Create Date: 2026-06-18 00:00:00.000000

"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'f18425943940'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite stores unique=True as a unique index, not a named constraint.
    # batch_alter_table drop_constraint won't find it — drop via raw SQL instead.
    op.execute('DROP INDEX IF EXISTS ix_stories_filename_base')
    op.execute('CREATE INDEX ix_stories_filename_base ON stories (filename_base)')


def downgrade():
    op.execute('DROP INDEX IF EXISTS ix_stories_filename_base')
    op.execute('CREATE UNIQUE INDEX ix_stories_filename_base ON stories (filename_base)')
