"""Reset watch_enabled to False for all existing authors

Revision ID: 20260503c
Revises: 20260503b
Create Date: 2026-05-03 00:02:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260503c'
down_revision = '20260503b'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE authors SET watch_enabled = 0")


def downgrade():
    pass
