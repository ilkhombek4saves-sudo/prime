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
    # ── 1. organizations table ──────────────────────────────────────────────
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

    # Insert default org so FK constraints work for existing rows
    op.execute(sa.text(
        f"INSERT INTO organizations (id, name, slug, active, created_at, updated_at) "
        f"VALUES ('{_DEFAULT_ORG_ID}'::uuid, 'Default', '{_DEFAULT_ORG_SLUG}', true, now(), now()) "
        f"ON CONFLICT DO NOTHING"
    ))

    # ── 2. Add org_id FK to existing tables (nullable, backfilled to default) ─
    for table in ("users", "bots", "agents", "providers"):
        op.add_column(
            table,
            sa.Column(
                "org_id",
                UUID(as_uuid=True),
                sa.ForeignKey("organizations.id"),
                nullable=True,
            ),
        )
        op.execute(sa.text(
            f"UPDATE {table} SET org_id = '{_DEFAULT_ORG_ID}'::uuid WHERE org_id IS NULL"
        ))

    # ── 3. knowledge_bases ──────────────────────────────────────────────────
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

    # ── 4. documents ────────────────────────────────────────────────────────
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

    # ── 5. document_chunks ─────────────────────────────────────────────────
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

    op.create_index("ix_document_chunks_kb", "document_chunks", ["knowledge_base_id", "chunk_index"])
    op.create_index("ix_documents_kb_status", "documents", ["knowledge_base_id", "status"])


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")

    for table in ("users", "bots", "agents", "providers"):
        op.drop_column(table, "org_id")

    op.drop_table("organizations")
    op.execute("DROP TYPE IF EXISTS documentstatus")
