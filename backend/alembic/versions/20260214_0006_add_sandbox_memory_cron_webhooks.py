"""add sandbox_sessions, memories, cron_jobs, webhook_bindings

Revision ID: 20260214_0006
Revises: 20260213_0005
Create Date: 2026-02-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260214_0006"
down_revision = "20260213_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    def _index_exists(table: str, index: str) -> bool:
        if table not in existing_tables:
            return False
        return any(idx["name"] == index for idx in inspector.get_indexes(table))

    # ── 1. sandbox_sessions ────────────────────────────────────────────────
    if "sandbox_sessions" not in existing_tables:
        op.create_table(
            "sandbox_sessions",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("container_id", sa.String(128), nullable=False),
            sa.Column(
                "status",
                sa.Enum("running", "stopped", "failed", name="sandboxstatus"),
                server_default="running",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        )
        existing_tables.add("sandbox_sessions")

    # ── 2. memories ────────────────────────────────────────────────────────
    if "memories" not in existing_tables:
        op.create_table(
            "memories",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("summary", sa.Text, nullable=True),
            sa.Column("embedding", sa.JSON, nullable=True),
            sa.Column("tags", sa.ARRAY(sa.String(128)), server_default="{}"),
            sa.Column("source", sa.String(64), server_default="conversation"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        existing_tables.add("memories")

    if not _index_exists("memories", "ix_memories_user_id"):
        op.create_index("ix_memories_user_id", "memories", ["user_id", "created_at"])

    # ── 3. cron_jobs ───────────────────────────────────────────────────────
    if "cron_jobs" not in existing_tables:
        op.create_table(
            "cron_jobs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("schedule", sa.String(128), nullable=False),
            sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("session_key", sa.String(255), nullable=True),
            sa.Column("active", sa.Boolean, server_default="true"),
            sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_run", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        existing_tables.add("cron_jobs")

    if not _index_exists("cron_jobs", "ix_cron_jobs_active"):
        op.create_index("ix_cron_jobs_active", "cron_jobs", ["active", "next_run"])

    # ── 4. webhook_bindings ────────────────────────────────────────────────
    if "webhook_bindings" not in existing_tables:
        op.create_table(
            "webhook_bindings",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("path", sa.String(255), unique=True, nullable=False),
            sa.Column("secret", sa.String(256), nullable=True),
            sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
            sa.Column("message_template", sa.Text, nullable=False),
            sa.Column("active", sa.Boolean, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        existing_tables.add("webhook_bindings")

    if not _index_exists("webhook_bindings", "ix_webhook_bindings_path"):
        op.create_index("ix_webhook_bindings_path", "webhook_bindings", ["path"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    def _index_exists(table: str, index: str) -> bool:
        if table not in existing_tables:
            return False
        return any(idx["name"] == index for idx in inspector.get_indexes(table))

    # Drop webhook_bindings
    if "webhook_bindings" in existing_tables:
        if _index_exists("webhook_bindings", "ix_webhook_bindings_path"):
            op.drop_index("ix_webhook_bindings_path", "webhook_bindings")
        op.drop_table("webhook_bindings")

    # Drop cron_jobs
    if "cron_jobs" in existing_tables:
        if _index_exists("cron_jobs", "ix_cron_jobs_active"):
            op.drop_index("ix_cron_jobs_active", "cron_jobs")
        op.drop_table("cron_jobs")

    # Drop memories
    if "memories" in existing_tables:
        if _index_exists("memories", "ix_memories_user_id"):
            op.drop_index("ix_memories_user_id", "memories")
        op.drop_table("memories")

    # Drop sandbox_sessions
    if "sandbox_sessions" in existing_tables:
        op.drop_table("sandbox_sessions")

    op.execute("DROP TYPE IF EXISTS sandboxstatus")
