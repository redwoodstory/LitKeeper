"""add progress tracking fields to download queue

Revision ID: 20260303
Revises: 202601071
Create Date: 2026-03-03 13:57:00

"""
from alembic import op
import sqlalchemy as sa

revision = '20260303'
down_revision = 'ef6a6d1622f8'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'download_queue' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('download_queue')]
        
        with op.batch_alter_table('download_queue', schema=None) as batch_op:
            if 'total_pages' not in existing_columns:
                batch_op.add_column(sa.Column('total_pages', sa.Integer(), nullable=True))
            
            if 'downloaded_pages' not in existing_columns:
                batch_op.add_column(sa.Column('downloaded_pages', sa.Integer(), nullable=True, server_default='0'))
            
            if 'file_size' not in existing_columns:
                batch_op.add_column(sa.Column('file_size', sa.Integer(), nullable=True))

def downgrade():
    with op.batch_alter_table('download_queue', schema=None) as batch_op:
        batch_op.drop_column('file_size')
        batch_op.drop_column('downloaded_pages')
        batch_op.drop_column('total_pages')
