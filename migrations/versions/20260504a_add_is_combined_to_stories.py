"""add is_combined to stories

Revision ID: 20260504a
Revises: 20260503c
Create Date: 2026-05-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260504a'
down_revision = 'ab6c413eb960'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('stories')}

    with op.batch_alter_table('stories', schema=None) as batch_op:
        if 'is_combined' not in existing_columns:
            batch_op.add_column(sa.Column('is_combined', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('stories', schema=None) as batch_op:
        batch_op.drop_column('is_combined')
