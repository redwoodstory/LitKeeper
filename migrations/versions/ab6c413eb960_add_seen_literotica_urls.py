"""add_seen_literotica_urls

Revision ID: ab6c413eb960
Revises: 20260503c
Create Date: 2026-05-04 09:30:36.946296

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab6c413eb960'
down_revision = '20260503c'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'seen_literotica_urls' not in inspector.get_table_names():
        op.create_table(
            'seen_literotica_urls',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('url', sa.String(length=512), nullable=False),
            sa.Column('story_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['story_id'], ['stories.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('seen_literotica_urls', schema=None) as batch_op:
            batch_op.create_index('ix_seen_literotica_urls_url', ['url'], unique=True)
            batch_op.create_index('ix_seen_literotica_urls_story_id', ['story_id'], unique=False)


def downgrade():
    with op.batch_alter_table('seen_literotica_urls', schema=None) as batch_op:
        batch_op.drop_index('ix_seen_literotica_urls_story_id')
        batch_op.drop_index('ix_seen_literotica_urls_url')
    op.drop_table('seen_literotica_urls')
