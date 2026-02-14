"""
SandboxService — Docker-based code execution sandbox.

Requires: pip install docker>=7.0
Docker socket must be mounted: /var/run/docker.sock:/var/run/docker.sock
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SANDBOX_IMAGE = "python:3.12-slim"
SANDBOX_PREFIX = "prime-sandbox-"
SANDBOX_MEMORY = "512m"
SANDBOX_CPUS = 0.5
SANDBOX_TIMEOUT = 60


def _get_docker_client():
    try:
        import docker
        return docker.from_env()
    except ImportError:
        raise RuntimeError("docker package not installed. Run: pip install docker>=7.0")
    except Exception as exc:
        raise RuntimeError(f"Cannot connect to Docker: {exc}") from exc


class SandboxService:
    """Manage isolated Docker containers for agent code execution."""

    @staticmethod
    def create_sandbox(
        session_id: str | None = None,
        workspace_path: str | None = None,
    ) -> str:
        """
        Create and start a sandbox container.
        Returns container_id.
        """
        client = _get_docker_client()
        container_name = f"{SANDBOX_PREFIX}{uuid.uuid4().hex[:8]}"

        volumes: dict = {}
        if workspace_path:
            volumes[workspace_path] = {"bind": "/workspace", "mode": "rw"}

        container = client.containers.run(
            SANDBOX_IMAGE,
            command="sleep infinity",
            name=container_name,
            detach=True,
            remove=True,
            mem_limit=SANDBOX_MEMORY,
            nano_cpus=int(SANDBOX_CPUS * 1e9),
            network_mode="none",
            security_opt=["no-new-privileges"],
            volumes=volumes,
        )
        logger.info("Sandbox created: %s (session=%s)", container.id[:12], session_id)

        # Persist to DB (best-effort)
        try:
            SandboxService._persist(session_id, container.id)
        except Exception as exc:
            logger.debug("Sandbox DB persist failed: %s", exc)

        return container.id

    @staticmethod
    def exec_in_sandbox(
        container_id: str,
        command: str,
        timeout: int = SANDBOX_TIMEOUT,
    ) -> tuple[str, str, int]:
        """
        Execute a shell command inside the sandbox.
        Returns (stdout, stderr, exit_code).
        """
        client = _get_docker_client()
        try:
            container = client.containers.get(container_id)
            exit_code, output = container.exec_run(
                ["sh", "-c", command],
                stdout=True,
                stderr=True,
                demux=True,
                environment={"PYTHONUNBUFFERED": "1"},
            )
            stdout_bytes, stderr_bytes = output if isinstance(output, tuple) else (output, b"")
            stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
            stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
            return stdout, stderr, exit_code
        except Exception as exc:
            return "", str(exc), 1

    @staticmethod
    def destroy_sandbox(container_id: str) -> None:
        """Stop and remove the sandbox container."""
        client = _get_docker_client()
        try:
            container = client.containers.get(container_id)
            container.stop(timeout=5)
            logger.info("Sandbox destroyed: %s", container_id[:12])
        except Exception as exc:
            logger.warning("Sandbox destroy error: %s", exc)

        # Update DB (best-effort)
        try:
            SandboxService._update_status(container_id, "stopped")
        except Exception:
            pass

    @staticmethod
    def cleanup_orphans() -> int:
        """Remove stale prime-sandbox-* containers. Returns count removed."""
        client = _get_docker_client()
        removed = 0
        try:
            containers = client.containers.list(
                filters={"name": SANDBOX_PREFIX, "status": "running"}
            )
            for c in containers:
                try:
                    c.stop(timeout=3)
                    removed += 1
                    logger.info("Orphan sandbox removed: %s", c.id[:12])
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("Cleanup orphans error: %s", exc)
        return removed

    # ── DB helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _persist(session_id: str | None, container_id: str) -> None:
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import SandboxSession
        import uuid as _uuid

        with SyncSessionLocal() as db:
            record = SandboxSession(
                session_id=_uuid.UUID(session_id) if session_id else None,
                container_id=container_id,
            )
            db.add(record)
            db.commit()

    @staticmethod
    def _update_status(container_id: str, status: str) -> None:
        from app.persistence.database import SyncSessionLocal
        from app.persistence.models import SandboxSession, SandboxStatus
        from sqlalchemy import select

        with SyncSessionLocal() as db:
            result = db.execute(
                select(SandboxSession).where(SandboxSession.container_id == container_id)
            )
            rec = result.scalar_one_or_none()
            if rec:
                rec.status = SandboxStatus(status)
                rec.stopped_at = datetime.now(timezone.utc)
                db.commit()
