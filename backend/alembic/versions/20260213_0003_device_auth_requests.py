"""Add device_auth_requests table for OAuth device flow.

Revision ID: 20260213_0003
Revises: 20260212_0002
Create Date: 2026-02-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

revision = "20260213_0003"
down_revision = "20260212_0002"
branch_labels = None
depends_on = None

_STATUS_ENUM_NAME = "deviceauthstatus"
_STATUS_VALUES = ("pending", "approved", "consumed", "denied", "expired")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deviceauthstatus') THEN
                    CREATE TYPE deviceauthstatus AS ENUM ('pending', 'approved', 'consumed', 'denied', 'expired');
                END IF;
            END$$;
            """
        )
    )
    status_enum = postgresql.ENUM(*_STATUS_VALUES, name=_STATUS_ENUM_NAME, create_type=False)

    if "device_auth_requests" in inspector.get_table_names():
        return

    op.create_table(
        "device_auth_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("device_code_hash", sa.String(128), unique=True, nullable=False),
        sa.Column("user_code", sa.String(32), unique=True, nullable=False),
        sa.Column("client_name", sa.String(128), nullable=False, server_default="prime-cli"),
        sa.Column("scope", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", status_enum, nullable=False, server_default="pending"),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_device_auth_requests_status_expires_at",
        "device_auth_requests",
        ["status", "expires_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "device_auth_requests" in existing_tables:
        indexes = [idx["name"] for idx in inspector.get_indexes("device_auth_requests")]
        if "ix_device_auth_requests_status_expires_at" in indexes:
            op.drop_index("ix_device_auth_requests_status_expires_at", table_name="device_auth_requests")
        op.drop_table("device_auth_requests")

    op.execute(f"DROP TYPE IF EXISTS {_STATUS_ENUM_NAME}")
