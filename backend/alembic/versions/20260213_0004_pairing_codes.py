"""Add pairing code to pairing_requests.

Revision ID: 20260213_0004
Revises: 20260213_0003
Create Date: 2026-02-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260213_0004"
down_revision = "20260213_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "pairing_requests" not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns("pairing_requests")}
    if "code" not in columns:
        op.add_column("pairing_requests", sa.Column("code", sa.String(16), nullable=True))

    # Unique index for quick lookup
    indexes = {idx["name"] for idx in inspector.get_indexes("pairing_requests")}
    if "ux_pairing_requests_code" not in indexes:
        op.create_index("ux_pairing_requests_code", "pairing_requests", ["code"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "pairing_requests" not in inspector.get_table_names():
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("pairing_requests")}
    if "ux_pairing_requests_code" in indexes:
        op.drop_index("ux_pairing_requests_code", table_name="pairing_requests")

    columns = {c["name"] for c in inspector.get_columns("pairing_requests")}
    if "code" in columns:
        op.drop_column("pairing_requests", "code")
