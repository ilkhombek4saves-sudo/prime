"""
BrowserService — Python client for the Node.js Playwright bridge.

The bridge runs as a separate process/container at BRIDGE_URL.
This service starts the Node.js process if not already running and forwards
all browser actions via HTTP to it.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BRIDGE_URL = os.environ.get("BROWSER_BRIDGE_URL", "http://localhost:3001")
BRIDGE_START_TIMEOUT = 15  # seconds
_bridge_process: Optional[subprocess.Popen] = None


class BrowserService:
    """HTTP client wrapper for the Playwright Node.js bridge."""

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    @staticmethod
    def ensure_running() -> bool:
        """Check if bridge is healthy; start it if not."""
        global _bridge_process
        try:
            resp = httpx.get(f"{BRIDGE_URL}/health", timeout=3)
            if resp.status_code == 200:
                return True
        except Exception:
            pass

        # Try to start the bridge process
        browser_dir = Path(__file__).parent.parent.parent.parent / "browser"
        if not browser_dir.exists():
            logger.warning("Browser bridge directory not found: %s", browser_dir)
            return False

        server_js = browser_dir / "server.js"
        if not server_js.exists():
            logger.warning("Browser bridge server.js not found")
            return False

        try:
            _bridge_process = subprocess.Popen(
                ["node", str(server_js)],
                cwd=str(browser_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait for bridge to become healthy
            deadline = time.time() + BRIDGE_START_TIMEOUT
            while time.time() < deadline:
                try:
                    resp = httpx.get(f"{BRIDGE_URL}/health", timeout=2)
                    if resp.status_code == 200:
                        logger.info("Browser bridge started (pid=%d)", _bridge_process.pid)
                        return True
                except Exception:
                    time.sleep(0.5)
            logger.warning("Browser bridge did not start in time")
        except Exception as exc:
            logger.error("Failed to start browser bridge: %s", exc)
        return False

    @staticmethod
    def stop() -> None:
        """Kill the bridge process on shutdown."""
        global _bridge_process
        if _bridge_process and _bridge_process.poll() is None:
            _bridge_process.terminate()
            _bridge_process = None
            logger.info("Browser bridge stopped")

    # ── Browser actions ────────────────────────────────────────────────────────

    @staticmethod
    def _post(endpoint: str, data: dict, timeout: int = 30) -> dict:
        try:
            resp = httpx.post(f"{BRIDGE_URL}{endpoint}", json=data, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            return {"error": "Browser bridge not running. Call browser_open first."}
        except Exception as exc:
            return {"error": str(exc)}

    @staticmethod
    def open(url: str, session_id: str, headless: bool = True) -> dict:
        return BrowserService._post(
            "/open", {"url": url, "session_id": session_id, "headless": headless}
        )

    @staticmethod
    def snapshot(session_id: str, full_page: bool = False) -> dict:
        return BrowserService._post(
            "/snapshot", {"session_id": session_id, "full_page": full_page}, timeout=60
        )

    @staticmethod
    def click(session_id: str, selector: str) -> dict:
        return BrowserService._post(
            "/click", {"session_id": session_id, "ref": selector}
        )

    @staticmethod
    def type_text(session_id: str, selector: str, text: str) -> dict:
        return BrowserService._post(
            "/type", {"session_id": session_id, "ref": selector, "text": text}
        )

    @staticmethod
    def fill(session_id: str, selector: str, value: str) -> dict:
        return BrowserService._post(
            "/fill", {"session_id": session_id, "selector": selector, "value": value}
        )

    @staticmethod
    def scroll(session_id: str, direction: str = "down", amount: int = 300) -> dict:
        return BrowserService._post(
            "/scroll", {"session_id": session_id, "direction": direction, "amount": amount}
        )

    @staticmethod
    def navigate(session_id: str, url: str) -> dict:
        return BrowserService._post(
            "/navigate", {"session_id": session_id, "url": url}
        )

    @staticmethod
    def extract(session_id: str, selector: str) -> dict:
        return BrowserService._post(
            "/extract", {"session_id": session_id, "selector": selector}
        )

    @staticmethod
    def close(session_id: str) -> dict:
        return BrowserService._post("/close", {"session_id": session_id})

    @staticmethod
    def list_sessions() -> dict:
        try:
            resp = httpx.get(f"{BRIDGE_URL}/sessions", timeout=5)
            return resp.json()
        except Exception as exc:
            return {"error": str(exc), "sessions": []}
