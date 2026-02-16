"""Add session summary field

Revision ID: 20260214_0008
Revises: 20260214_0007
Create Date: 2026-02-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '20260214_0008'
down_revision = '20260214_0007'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    # Add summary fields to sessions table (if not exists)
    if not column_exists('sessions', 'summary'):
        op.add_column('sessions', sa.Column('summary', sa.Text(), nullable=True, default=''))
    if not column_exists('sessions', 'summary_updated_at'):
        op.add_column('sessions', sa.Column('summary_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if column_exists('sessions', 'summary_updated_at'):
        op.drop_column('sessions', 'summary_updated_at')
    if column_exists('sessions', 'summary'):
        op.drop_column('sessions', 'summary')
