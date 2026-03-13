"""add in_queue to stories

Revision ID: 20260313b
Revises: 20260313
Create Date: 2026-03-13 13:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = '20260313b'
down_revision = '20260313'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('stories', sa.Column('in_queue', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_column('stories', 'in_queue')
    except Exception:
        pass
