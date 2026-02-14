"""Add node execution and approval queue tables for OpenClaw-style workflow.

Revision ID: 20260214_0007
Revises: 20260214_0006
Create Date: 2026-02-14 12:00:00.000000+00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260214_0007"
down_revision: Union[str, None] = "20260214_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create execution_status enum with checkfirst
    execution_status_enum = sa.Enum(
        "pending", "pending_approval", "approved", "rejected",
        "in_progress", "completed", "failed", "canceled",
        name="executionstatus"
    )
    execution_status_enum.create(op.get_bind(), checkfirst=True)

    # Create node_executions table - use varchar for status to avoid enum issues
    op.create_table(
        "node_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("connection_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("node_name", sa.String(128), nullable=False, server_default="unknown"),
        sa.Column("command", sa.String(128), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("working_dir", sa.Text(), nullable=True),
        sa.Column("env_vars", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approval_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Create indexes for node_executions
    op.create_index("ix_node_executions_status", "node_executions", ["status", "created_at"])
    op.create_index("ix_node_executions_connection", "node_executions", ["connection_id", "created_at"])
    op.create_index("ix_node_executions_idempotency", "node_executions", ["idempotency_key"])

    # Create node_approval_queue table
    op.create_table(
        "node_approval_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("node_executions.id"), nullable=False),
        sa.Column("connection_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("node_name", sa.String(128), nullable=False, server_default="unknown"),
        sa.Column("command", sa.String(128), nullable=False),
        sa.Column("params_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("auto_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("auto_approval_rule", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Create indexes for node_approval_queue
    op.create_index("ix_node_approval_queue_status", "node_approval_queue", ["status", "created_at"])
    op.create_index("ix_node_approval_queue_expires", "node_approval_queue", ["expires_at", "status"])
    op.create_index("ix_node_approval_queue_connection", "node_approval_queue", ["connection_id"])


def downgrade() -> None:
    # Drop tables
    op.drop_table("node_approval_queue")
    op.drop_table("node_executions")
    
    # Drop enum
    execution_status_enum = sa.Enum(
        "pending", "pending_approval", "approved", "rejected",
        "in_progress", "completed", "failed", "canceled",
        name="executionstatus"
    )
    execution_status_enum.drop(op.get_bind())
