"""Add organizations, knowledge bases, RAG chunks; add org_id to main entities.

Revision ID: 20260212_0002
Revises: 20260212_0001
Create Date: 2026-02-12
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260212_0002"
down_revision = "20260212_0001"
branch_labels = None
depends_on = None

_DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"
_DEFAULT_ORG_SLUG = "default"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    def _column_exists(table: str, column: str) -> bool:
        if table not in existing_tables:
            return False
        return any(col["name"] == column for col in inspector.get_columns(table))

    def _index_exists(table: str, index: str) -> bool:
        if table not in existing_tables:
            return False
        return any(idx["name"] == index for idx in inspector.get_indexes(table))

    # ── 1. organizations table ──────────────────────────────────────────────
    if "organizations" not in existing_tables:
        op.create_table(
            "organizations",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column("name", sa.String(128), unique=True, nullable=False),
            sa.Column("slug", sa.String(64), unique=True, nullable=False),
            sa.Column("active", sa.Boolean(), default=True, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        existing_tables.add("organizations")

    # Insert default org so FK constraints work for existing rows
    op.execute(sa.text(
        f"INSERT INTO organizations (id, name, slug, active, created_at, updated_at) "
        f"VALUES ('{_DEFAULT_ORG_ID}'::uuid, 'Default', '{_DEFAULT_ORG_SLUG}', true, now(), now()) "
        f"ON CONFLICT DO NOTHING"
    ))

    # ── 2. Add org_id FK to existing tables (nullable, backfilled to default) ─
    for table in ("users", "bots", "agents", "providers"):
        if not _column_exists(table, "org_id"):
            op.add_column(
                table,
                sa.Column(
                    "org_id",
                    UUID(as_uuid=True),
                    sa.ForeignKey("organizations.id"),
                    nullable=True,
                ),
            )
        if table in existing_tables:
            op.execute(
                sa.text(
                    f"UPDATE {table} SET org_id = '{_DEFAULT_ORG_ID}'::uuid WHERE org_id IS NULL"
                )
            )

    # ── 3. knowledge_bases ──────────────────────────────────────────────────
    if "knowledge_bases" not in existing_tables:
        op.create_table(
            "knowledge_bases",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
            sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), default=""),
            sa.Column("active", sa.Boolean(), default=True, nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
        )
        existing_tables.add("knowledge_bases")

    # ── 4. documents ────────────────────────────────────────────────────────
    if "documents" not in existing_tables:
        op.create_table(
            "documents",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "knowledge_base_id",
                UUID(as_uuid=True),
                sa.ForeignKey("knowledge_bases.id"),
                nullable=False,
            ),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(64), default="text/plain"),
            sa.Column("size_bytes", sa.Integer(), default=0),
            sa.Column(
                "status",
                sa.Enum(
                    "pending", "indexing", "indexed", "failed", name="documentstatus"
                ),
                default="pending",
                nullable=False,
            ),
            sa.Column("chunk_count", sa.Integer(), default=0),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("meta", sa.JSON(), server_default="{}"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
        )
        existing_tables.add("documents")

    # ── 5. document_chunks ─────────────────────────────────────────────────
    if "document_chunks" not in existing_tables:
        op.create_table(
            "document_chunks",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "document_id",
                UUID(as_uuid=True),
                sa.ForeignKey("documents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "knowledge_base_id",
                UUID(as_uuid=True),
                sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("embedding", sa.JSON(), nullable=True),  # vector stored as JSON list
            sa.Column("meta", sa.JSON(), default=dict),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
        )
        existing_tables.add("document_chunks")

    if not _index_exists("document_chunks", "ix_document_chunks_kb"):
        op.create_index(
            "ix_document_chunks_kb", "document_chunks", ["knowledge_base_id", "chunk_index"]
        )
    if not _index_exists("documents", "ix_documents_kb_status"):
        op.create_index("ix_documents_kb_status", "documents", ["knowledge_base_id", "status"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "document_chunks" in existing_tables:
        op.drop_table("document_chunks")
    if "documents" in existing_tables:
        op.drop_table("documents")
    if "knowledge_bases" in existing_tables:
        op.drop_table("knowledge_bases")

    for table in ("users", "bots", "agents", "providers"):
        if table in existing_tables:
            columns = [col["name"] for col in inspector.get_columns(table)]
            if "org_id" in columns:
                op.drop_column(table, "org_id")

    if "organizations" in existing_tables:
        op.drop_table("organizations")
    op.execute("DROP TYPE IF EXISTS documentstatus")
