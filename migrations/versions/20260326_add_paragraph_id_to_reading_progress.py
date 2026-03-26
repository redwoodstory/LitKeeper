"""add paragraph_id to reading_progress

Revision ID: 20260326
Revises: 20260313c
Create Date: 2026-03-26 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = '20260326'
down_revision = '20260313c'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('reading_progress')}

    if 'paragraph_id' not in existing_columns:
        op.add_column('reading_progress', sa.Column('paragraph_id', sa.Text(), nullable=True))


def downgrade():
    try:
        op.drop_column('reading_progress', 'paragraph_id')
    except Exception:
        pass
