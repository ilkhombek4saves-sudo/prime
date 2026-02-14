"""Add session summary field

Revision ID: 20260214_0008
Revises: 20260214_0007
Create Date: 2026-02-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260214_0008'
down_revision = '20260214_0007'
branch_labels = None
depends_on = None


def upgrade():
    # Add summary fields to sessions table
    op.add_column('sessions', sa.Column('summary', sa.Text(), nullable=True, default=''))
    op.add_column('sessions', sa.Column('summary_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('sessions', 'summary_updated_at')
    op.drop_column('sessions', 'summary')
