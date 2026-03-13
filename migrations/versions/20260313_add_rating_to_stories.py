"""add rating to stories

Revision ID: 20260313
Revises: 20260303
Create Date: 2026-03-13 12:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = '20260313'
down_revision = '20260303'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('stories', sa.Column('rating', sa.Integer(), nullable=True))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_column('stories', 'rating')
    except Exception:
        pass
