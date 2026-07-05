"""add chapter_order to download_queue

Revision ID: 20260704a
Revises: 91eb3b2b1034
Create Date: 2026-07-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260704a'
down_revision = '91eb3b2b1034'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('download_queue')}

    with op.batch_alter_table('download_queue', schema=None) as batch_op:
        if 'chapter_order' not in existing_columns:
            batch_op.add_column(sa.Column('chapter_order', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('download_queue', schema=None) as batch_op:
        batch_op.drop_column('chapter_order')
