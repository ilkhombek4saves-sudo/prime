"""
SandboxService — secure command execution in Docker containers.

Replaces direct subprocess calls with isolated container execution.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound

logger = logging.getLogger(__name__)

DEFAULT_SANDBOX_IMAGE = "alpine:latest"
DEFAULT_TIMEOUT = 60
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_CPU_LIMIT = "1.0"


class SandboxError(Exception):
    """Sandbox execution error."""
    pass


class SandboxService:
    """Execute commands in isolated Docker containers."""

    _client: docker.DockerClient | None = None

    @classmethod
    def _get_client(cls) -> docker.DockerClient:
        if cls._client is None:
            try:
                cls._client = docker.from_env()
            except DockerException as e:
                raise SandboxError(f"Docker not available: {e}") from e
        return cls._client

    @classmethod
    async def run_command(
        cls,
        command: str | list[str],
        *,
        working_dir: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: str = DEFAULT_CPU_LIMIT,
        env_vars: dict[str, str] | None = None,
        network_mode: str = "none",  # No network by default for security
        allow_network: bool = False,
    ) -> dict[str, Any]:
        """
        Execute a command in a sandboxed Docker container.

        Args:
            command: Shell command or list of command arguments
            working_dir: Host directory to mount as /workspace
            timeout: Maximum execution time in seconds
            memory_limit: Memory limit (e.g., '512m', '1g')
            cpu_limit: CPU limit (e.g., '1.0', '0.5')
            env_vars: Environment variables to set
            network_mode: Docker network mode
            allow_network: If True, allow network access (use with caution)

        Returns:
            Dict with stdout, stderr, exit_code, and duration_ms
        """
        client = cls._get_client()
        container_name = f"prime-sandbox-{uuid.uuid4().hex[:12]}"

        # Ensure sandbox image exists
        try:
            client.images.get(DEFAULT_SANDBOX_IMAGE)
        except ImageNotFound:
            logger.info("Pulling sandbox image %s...", DEFAULT_SANDBOX_IMAGE)
            try:
                client.images.pull(DEFAULT_SANDBOX_IMAGE)
            except DockerException as e:
                raise SandboxError(f"Failed to pull sandbox image: {e}") from e

        # Prepare command
        if isinstance(command, list):
            cmd = command
        else:
            cmd = ["sh", "-c", command]

        # Prepare volumes
        volumes = {}
        if working_dir and os.path.isdir(working_dir):
            volumes[os.path.abspath(working_dir)] = {
                "bind": "/workspace",
                "mode": "rw",
            }

        # Environment variables
        environment = dict(env_vars or {})
        environment["HOME"] = "/tmp"
        environment["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

        # Network mode
        actual_network = "bridge" if allow_network else network_mode

        logger.info(
            "Sandbox: running command in container %s (timeout=%ds, mem=%s, cpu=%s, network=%s)",
            container_name,
            timeout,
            memory_limit,
            cpu_limit,
            actual_network,
        )

        container = None
        start_time = asyncio.get_event_loop().time()

        try:
            # Run container with resource limits
            container = client.containers.run(
                DEFAULT_SANDBOX_IMAGE,
                cmd,
                name=container_name,
                volumes=volumes,
                environment=environment,
                network_mode=actual_network,
                mem_limit=memory_limit,
                cpu_quota=int(float(cpu_limit) * 100000),  # Convert to microseconds
                cpu_period=100000,
                detach=True,
                stdout=True,
                stderr=True,
                working_dir="/workspace" if working_dir else "/tmp",
                # Security options
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                read_only=False,  # Allow writing to /tmp and /workspace
            )

            # Wait for completion with timeout
            loop = asyncio.get_event_loop()
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, container.wait),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("Sandbox: command timed out after %ds", timeout)
                try:
                    container.kill()
                except Exception:
                    pass
                raise SandboxError(f"Command timed out after {timeout} seconds")

            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            exit_code = result.get("StatusCode", -1)

            # Get logs
            logs = await loop.run_in_executor(None, container.logs, True, True)
            logs_str = logs.decode("utf-8", errors="replace") if logs else ""

            # Split stdout/stderr (Docker combines them)
            stdout = logs_str
            stderr = ""

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "container_name": container_name,
            }

        except DockerException as e:
            raise SandboxError(f"Docker execution failed: {e}") from e

        finally:
            # Cleanup container
            if container:
                try:
                    container.remove(force=True)
                except Exception as e:
                    logger.warning("Failed to remove sandbox container: %s", e)

    @classmethod
    def validate_command(cls, command: str, allowed_patterns: list[str] | None = None) -> bool:
        """
        Validate that a command matches allowed patterns.

        Args:
            command: The command string to validate
            allowed_patterns: List of allowed command patterns (regex or substring)

        Returns:
            True if command is allowed
        """
        import re

        if allowed_patterns is None:
            # Default: allow common safe commands
            allowed_patterns = [
                r"^python[3]?\s+-m\s+(pytest|unittest|pip|black|ruff|mypy)",
                r"^(pip|npm|yarn|cargo|go)\s+(install|build|test|run|lint)",
                r"^(git|ls|cat|echo|head|tail|wc|grep|find|mkdir|touch|cp|mv|rm|rmdir)\s",
                r"^(curl|wget)\s+(-[A-Za-z]+\s+)*https?://",
                r"^(docker-compose|docker)\s+(ps|logs|build|up|down|exec|run)\s",
                r"^(make|cmake|gradle|mvn)\s",
                r"^(pytest|test|lint|format|build|install)\s",
            ]

        for pattern in allowed_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return True

        return False

    @classmethod
    def is_available(cls) -> bool:
        """Check if Docker sandbox is available."""
        try:
            client = cls._get_client()
            client.ping()
            return True
        except Exception:
            return False


# Convenience function for direct use
def run_sandboxed(
    command: str | list[str],
    working_dir: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Run a command in sandbox (sync wrapper for convenience).
    
    For async usage, use SandboxService.run_command()
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(
        SandboxService.run_command(command, working_dir=working_dir, **kwargs)
    )
