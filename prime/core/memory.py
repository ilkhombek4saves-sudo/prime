"""Persistent memory system — stores conversation history, user facts, session state"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from prime.config.settings import DB_PATH


class MemoryDB:
    """SQLite-backed persistent memory store."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL DEFAULT 'cli',
                    user_id TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    meta TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    user_id TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    command TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run REAL,
                    next_run REAL,
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);
                CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);
            """)

    # ── Sessions ──────────────────────────────────────────────────────────
    def create_session(self, session_id: str, channel: str = "cli", user_id: str = None) -> None:
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, channel, user_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, channel, user_id, now, now),
            )

    def get_session(self, session_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_session(self, session_id: str, meta: dict = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (time.time(), session_id),
            )

    def list_sessions(self, channel: str = None, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            if channel:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE channel = ? ORDER BY updated_at DESC LIMIT ?",
                    (channel, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Messages ──────────────────────────────────────────────────────────
    def add_message(self, session_id: str, role: str, content: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, time.time()),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (time.time(), session_id),
            )

    def get_messages(self, session_id: str, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def get_conversation(self, session_id: str, limit: int = 20) -> list[dict]:
        """Return messages in LLM-ready format."""
        msgs = self.get_messages(session_id, limit)
        return [{"role": m["role"], "content": m["content"]} for m in msgs
                if m["role"] in ("user", "assistant")]

    # ── Facts / Memory ────────────────────────────────────────────────────
    def save_memory(self, key: str, content: str, user_id: str = None) -> None:
        now = time.time()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM memories WHERE key = ? AND user_id IS ?",
                (key, user_id),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE memories SET content = ?, updated_at = ? WHERE id = ?",
                    (content, now, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO memories (key, content, user_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (key, content, user_id, now, now),
                )

    def get_memory(self, key: str, user_id: str = None) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT content FROM memories WHERE key = ? AND user_id IS ?",
                (key, user_id),
            ).fetchone()
            return row["content"] if row else None

    def search_memories(self, query: str, user_id: str = None, limit: int = 5) -> list[dict]:
        with self._conn() as conn:
            q = f"%{query.lower()}%"
            if user_id:
                rows = conn.execute(
                    "SELECT key, content FROM memories WHERE user_id = ? "
                    "AND (lower(key) LIKE ? OR lower(content) LIKE ?) LIMIT ?",
                    (user_id, q, q, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key, content FROM memories WHERE "
                    "(lower(key) LIKE ? OR lower(content) LIKE ?) LIMIT ?",
                    (q, q, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def list_memories(self, user_id: str = None) -> list[dict]:
        with self._conn() as conn:
            if user_id:
                rows = conn.execute(
                    "SELECT key, content, updated_at FROM memories WHERE user_id = ? "
                    "ORDER BY updated_at DESC",
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key, content, updated_at FROM memories ORDER BY updated_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Scheduled Tasks ───────────────────────────────────────────────────
    def save_task(self, name: str, schedule: str, command: str) -> int:
        now = time.time()
        with self._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (name, schedule, command, created_at) VALUES (?, ?, ?, ?)",
                (name, schedule, command, now),
            )
            return cursor.lastrowid

    def list_tasks(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_task(self, task_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    # ── Stats ─────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        with self._conn() as conn:
            sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            memories = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE enabled = 1").fetchone()[0]
            return {
                "sessions": sessions,
                "messages": messages,
                "memories": memories,
                "active_tasks": tasks,
            }


# Singleton
_db: MemoryDB | None = None


def get_db() -> MemoryDB:
    global _db
    if _db is None:
        _db = MemoryDB()
    return _db
