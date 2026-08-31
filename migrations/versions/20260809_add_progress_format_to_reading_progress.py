"""add progress_format to reading_progress

Revision ID: 20260809
Revises: 20260326
Create Date: 2026-08-09 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = '20260809'
down_revision = '91eb3b2b1034'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('reading_progress')}

    if 'progress_format' not in existing_columns:
        op.add_column('reading_progress', sa.Column('progress_format', sa.String(length=10), nullable=True))


def downgrade():
    try:
        op.drop_column('reading_progress', 'progress_format')
    except Exception:
        pass
