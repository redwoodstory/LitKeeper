"""add_auto_refresh_exclusion_type

Revision ID: ef6a6d1622f8
Revises: 32fa88073645
Create Date: 2026-01-08 09:22:55.294659

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef6a6d1622f8'
down_revision = '32fa88073645'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('stories')]
    
    with op.batch_alter_table('stories', schema=None) as batch_op:
        if 'auto_refresh_exclusion_type' not in columns:
            batch_op.add_column(sa.Column('auto_refresh_exclusion_type', sa.String(length=50), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('stories')]
    
    with op.batch_alter_table('stories', schema=None) as batch_op:
        if 'auto_refresh_exclusion_type' in columns:
            batch_op.drop_column('auto_refresh_exclusion_type')
