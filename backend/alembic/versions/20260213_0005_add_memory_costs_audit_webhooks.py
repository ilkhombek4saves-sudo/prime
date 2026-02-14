"""add user_memories, cost_records, audit_logs, webhook_endpoints tables

Revision ID: 20260213_0005
Revises: 20260213_0004
Create Date: 2026-02-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260213_0005"
down_revision = "20260213_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if tables already exist (for idempotent migrations)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if "user_memories" not in existing_tables:
        op.create_table(
            "user_memories",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
            sa.Column("key", sa.String(255), nullable=False),
            sa.Column("value", sa.Text, nullable=False),
            sa.Column("category", sa.String(64), server_default="fact"),
            sa.Column("confidence", sa.Float, server_default="1.0"),
            sa.Column("source_session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("active", sa.Boolean, server_default="true"),
            sa.Column("access_count", sa.Integer, server_default="0"),
            sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_user_memories_user_agent", "user_memories", ["user_id", "agent_id"])

    if "cost_records" not in existing_tables:
        op.create_table(
            "cost_records",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
            sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("providers.id"), nullable=True),
            sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("model", sa.String(128), nullable=False),
            sa.Column("input_tokens", sa.Integer, server_default="0"),
            sa.Column("output_tokens", sa.Integer, server_default="0"),
            sa.Column("cost_usd", sa.Float, server_default="0"),
            sa.Column("channel", sa.String(64), server_default="telegram"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_cost_records_created", "cost_records", ["created_at", "org_id"])
        op.create_index("ix_cost_records_agent", "cost_records", ["agent_id", "created_at"])

    if "audit_logs" not in existing_tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
            sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("action", sa.String(128), nullable=False),
            sa.Column("resource_type", sa.String(64), nullable=False),
            sa.Column("resource_id", sa.String(128), nullable=True),
            sa.Column("details", sa.JSON, server_default="{}"),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_audit_logs_action", "audit_logs", ["action", "created_at"])

    if "webhook_endpoints" not in existing_tables:
        op.create_table(
            "webhook_endpoints",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
            sa.Column("url", sa.Text, nullable=False),
            sa.Column("secret", sa.String(255), nullable=True),
            sa.Column("events", sa.ARRAY(sa.String(64)), server_default="{}"),
            sa.Column("active", sa.Boolean, server_default="true"),
            sa.Column("failure_count", sa.Integer, server_default="0"),
            sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if "webhook_endpoints" in existing_tables:
        op.drop_table("webhook_endpoints")
    if "audit_logs" in existing_tables:
        op.drop_table("audit_logs")
    if "cost_records" in existing_tables:
        op.drop_table("cost_records")
    if "user_memories" in existing_tables:
        op.drop_table("user_memories")
