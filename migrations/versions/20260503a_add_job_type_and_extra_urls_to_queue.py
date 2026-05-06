"""add job_type, extra_urls, scheduled_after to download_queue

Revision ID: 20260503a
Revises: 7097b9a2bfee
Create Date: 2026-05-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260503a'
down_revision = '7097b9a2bfee'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('download_queue')}

    with op.batch_alter_table('download_queue', schema=None) as batch_op:
        if 'job_type' not in existing_columns:
            batch_op.add_column(sa.Column('job_type', sa.String(length=20), nullable=False, server_default='single'))
        if 'extra_urls' not in existing_columns:
            batch_op.add_column(sa.Column('extra_urls', sa.Text(), nullable=True))
        if 'scheduled_after' not in existing_columns:
            batch_op.add_column(sa.Column('scheduled_after', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('download_queue', schema=None) as batch_op:
        batch_op.drop_column('scheduled_after')
        batch_op.drop_column('extra_urls')
        batch_op.drop_column('job_type')
