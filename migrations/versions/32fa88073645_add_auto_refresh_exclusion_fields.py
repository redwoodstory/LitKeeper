"""add_auto_refresh_exclusion_fields

Revision ID: 32fa88073645
Revises: 202601071
Create Date: 2026-01-07 16:27:05.966802

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '32fa88073645'
down_revision = '202601071'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('stories')]
    
    with op.batch_alter_table('stories', schema=None) as batch_op:
        if 'auto_refresh_excluded' not in columns:
            batch_op.add_column(sa.Column('auto_refresh_excluded', sa.Boolean(), nullable=False, server_default='0'))
        if 'auto_refresh_exclusion_reason' not in columns:
            batch_op.add_column(sa.Column('auto_refresh_exclusion_reason', sa.String(length=500), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('stories')]
    
    with op.batch_alter_table('stories', schema=None) as batch_op:
        if 'auto_refresh_exclusion_reason' in columns:
            batch_op.drop_column('auto_refresh_exclusion_reason')
        if 'auto_refresh_excluded' in columns:
            batch_op.drop_column('auto_refresh_excluded')
