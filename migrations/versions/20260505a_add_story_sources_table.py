"""add_story_sources_table

Revision ID: 20260505a
Revises: 20260504a
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa

revision = '20260505a'
down_revision = '20260504a'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'story_sources' not in existing_tables:
        op.create_table(
            'story_sources',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('story_id', sa.Integer(), nullable=False),
            sa.Column('url', sa.String(length=512), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['story_id'], ['stories.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_story_sources_story_id', 'story_sources', ['story_id'])


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'story_sources' in existing_tables:
        op.drop_index('ix_story_sources_story_id', table_name='story_sources')
        op.drop_table('story_sources')
