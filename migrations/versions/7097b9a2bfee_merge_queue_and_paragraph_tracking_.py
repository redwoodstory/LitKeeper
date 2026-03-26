"""merge queue and paragraph tracking migrations

Revision ID: 7097b9a2bfee
Revises: 20260326, 20260326b
Create Date: 2026-03-26 15:38:01.171271

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7097b9a2bfee'
down_revision = ('20260326', '20260326b')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
