"""add description to stories

Revision ID: 20260313c
Revises: 20260313b
Create Date: 2026-03-13 14:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = '20260313c'
down_revision = '20260313b'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('stories', sa.Column('description', sa.Text(), nullable=True))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_column('stories', 'description')
    except Exception:
        pass
