"""
TailscaleService — wrapper around the Tailscale CLI.

Provides status, connect, serve, and funnel operations.
Requires tailscale CLI to be installed on the host or sidecar container.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TailscaleStatus:
    connected: bool
    hostname: str = ""
    tailnet_ip: str = ""
    peers: list[dict] | None = None
    funnel_url: str = ""


class TailscaleService:
    """Interact with the Tailscale daemon via its CLI."""

    @staticmethod
    def is_installed() -> bool:
        return shutil.which("tailscale") is not None

    @staticmethod
    def _run(*args: str, timeout: int = 30) -> tuple[str, str, int]:
        """Run a tailscale CLI command. Returns (stdout, stderr, returncode)."""
        try:
            result = subprocess.run(
                ["tailscale", *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except FileNotFoundError:
            return "", "tailscale CLI not found", 1
        except subprocess.TimeoutExpired:
            return "", "Command timed out", 1
        except Exception as exc:
            return "", str(exc), 1

    @staticmethod
    def status() -> TailscaleStatus:
        """Return current Tailscale status."""
        stdout, stderr, code = TailscaleService._run("status", "--json")
        if code != 0:
            return TailscaleStatus(connected=False)

        try:
            data = json.loads(stdout)
            backend = data.get("BackendState", "")
            connected = backend == "Running"
            self_node = data.get("Self", {})
            hostname = self_node.get("HostName", "")
            tailnet_ip = (self_node.get("TailscaleIPs") or [""])[0]
            peers = [
                {
                    "hostname": p.get("HostName", ""),
                    "ip": (p.get("TailscaleIPs") or [""])[0],
                    "online": p.get("Online", False),
                }
                for p in data.get("Peer", {}).values()
            ]
            # Try to get funnel URL
            funnel_url = ""
            if connected and hostname:
                funnel_url = f"https://{hostname}.ts.net"

            return TailscaleStatus(
                connected=connected,
                hostname=hostname,
                tailnet_ip=tailnet_ip,
                peers=peers,
                funnel_url=funnel_url,
            )
        except Exception as exc:
            logger.warning("Failed to parse tailscale status: %s", exc)
            return TailscaleStatus(connected=False)

    @staticmethod
    def connect(auth_key: str) -> tuple[bool, str]:
        """Run `tailscale up` with the given auth key."""
        stdout, stderr, code = TailscaleService._run(
            "up", f"--authkey={auth_key}", "--accept-routes", timeout=60
        )
        success = code == 0
        message = stdout or stderr
        return success, message

    @staticmethod
    def serve(port: int = 8000) -> tuple[bool, str]:
        """Expose a local port to the tailnet via `tailscale serve`."""
        stdout, stderr, code = TailscaleService._run(
            "serve", "--bg", str(port), timeout=30
        )
        success = code == 0
        return success, stdout or stderr

    @staticmethod
    def funnel(port: int = 8000) -> tuple[bool, str]:
        """Expose a local port to the public internet via `tailscale funnel`."""
        stdout, stderr, code = TailscaleService._run(
            "funnel", "--bg", str(port), timeout=30
        )
        success = code == 0
        return success, stdout or stderr

    @staticmethod
    def stop_funnel() -> tuple[bool, str]:
        """Stop the tailscale funnel."""
        stdout, stderr, code = TailscaleService._run("funnel", "--off", timeout=15)
        success = code == 0
        return success, stdout or stderr

    @staticmethod
    def get_funnel_url() -> str:
        """Return the public funnel URL if active."""
        status = TailscaleService.status()
        if status.connected and status.hostname:
            return f"https://{status.hostname}.ts.net"
        return ""
