"""add source_type to stories

Revision ID: 20260810
Revises: 20260809
Create Date: 2026-08-10 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = '20260810'
down_revision = '20260809'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('stories')}

    if 'source_type' not in existing_columns:
        op.add_column(
            'stories',
            sa.Column('source_type', sa.String(length=20), nullable=False, server_default='literotica')
        )
        op.create_index('ix_stories_source_type', 'stories', ['source_type'])


def downgrade():
    try:
        op.drop_index('ix_stories_source_type', table_name='stories')
    except Exception:
        pass
    try:
        op.drop_column('stories', 'source_type')
    except Exception:
        pass
