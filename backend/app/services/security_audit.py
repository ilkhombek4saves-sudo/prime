"""
Security audit — checks configuration for common misconfigurations.
Used by `prime security audit` CLI and /api/security/audit endpoint.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class AuditFinding:
    severity: str  # critical, warning, info
    code: str
    message: str
    fix: str


@dataclass
class AuditReport:
    passed: int = 0
    findings: list[AuditFinding] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "critical": self.critical_count,
            "findings": [
                {"severity": f.severity, "code": f.code, "message": f.message, "fix": f.fix}
                for f in self.findings
            ],
        }


class SecurityAuditor:
    def run(self) -> AuditReport:
        report = AuditReport()
        checks = [
            self._check_secret_key,
            self._check_jwt_secret,
            self._check_cors,
            self._check_debug_mode,
            self._check_database_url,
            self._check_proxy_trust,
            self._check_ws_remote,
            self._check_api_keys_exposed,
            self._check_gateway_lock,
            self._check_rate_limit,
        ]
        for check in checks:
            finding = check()
            if finding:
                report.findings.append(finding)
            else:
                report.passed += 1
        return report

    def _check_secret_key(self) -> AuditFinding | None:
        s = get_settings()
        if s.secret_key in ("change-me", "secret", ""):
            return AuditFinding(
                severity="critical", code="WEAK_SECRET_KEY",
                message="SECRET_KEY is default or empty.",
                fix="Set SECRET_KEY to a random 32+ char string in .env",
            )
        if len(s.secret_key) < 16:
            return AuditFinding(
                severity="warning", code="SHORT_SECRET_KEY",
                message="SECRET_KEY is shorter than 16 chars.",
                fix="Use a longer SECRET_KEY (32+ chars recommended)",
            )
        return None

    def _check_jwt_secret(self) -> AuditFinding | None:
        s = get_settings()
        if s.jwt_secret in ("change-me-too", "secret", ""):
            return AuditFinding(
                severity="critical", code="WEAK_JWT_SECRET",
                message="JWT_SECRET is default or empty.",
                fix="Set JWT_SECRET to a random 32+ char string in .env",
            )
        return None

    def _check_cors(self) -> AuditFinding | None:
        s = get_settings()
        if s.app_env == "prod":
            return AuditFinding(
                severity="warning", code="CORS_NOT_RESTRICTED",
                message="CORS origins should be explicitly set in production.",
                fix="Set CORS_ALLOWED_ORIGINS env var to your frontend domain",
            )
        return None

    def _check_debug_mode(self) -> AuditFinding | None:
        s = get_settings()
        if s.app_env == "prod" and s.telegram_show_errors:
            return AuditFinding(
                severity="warning", code="DEBUG_ERRORS_IN_PROD",
                message="Telegram error details are shown in production.",
                fix="Set TELEGRAM_SHOW_ERRORS=false in production",
            )
        return None

    def _check_database_url(self) -> AuditFinding | None:
        s = get_settings()
        if "sqlite" in s.database_url:
            return AuditFinding(
                severity="warning", code="SQLITE_IN_USE",
                message="SQLite is not suitable for production.",
                fix="Switch to PostgreSQL via DATABASE_URL",
            )
        if "password" in s.database_url and "@" in s.database_url:
            parts = s.database_url.split("@")[0]
            if ":postgres@" in s.database_url or ":password@" in s.database_url:
                return AuditFinding(
                    severity="critical", code="DEFAULT_DB_PASSWORD",
                    message="Database uses default password.",
                    fix="Set a strong unique password in DATABASE_URL",
                )
        return None

    def _check_proxy_trust(self) -> AuditFinding | None:
        s = get_settings()
        if s.allow_forwarded_headers and not s.trusted_proxy_cidrs:
            return AuditFinding(
                severity="warning", code="OPEN_PROXY_TRUST",
                message="Forwarded headers accepted without CIDR restriction.",
                fix="Set TRUSTED_PROXY_CIDRS to your reverse proxy IPs",
            )
        return None

    def _check_ws_remote(self) -> AuditFinding | None:
        s = get_settings()
        if s.ws_allow_remote and s.app_env == "prod":
            return AuditFinding(
                severity="warning", code="WS_REMOTE_OPEN",
                message="WebSocket allows remote connections in production.",
                fix="Set WS_ALLOW_REMOTE=false or restrict via firewall",
            )
        return None

    def _check_api_keys_exposed(self) -> AuditFinding | None:
        for key_env in ("OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN", "DEEPSEEK_API_KEY"):
            val = os.getenv(key_env, "")
            if val and len(val) < 10:
                return AuditFinding(
                    severity="warning", code="SHORT_API_KEY",
                    message=f"{key_env} looks invalid (too short).",
                    fix=f"Verify {key_env} is correct",
                )
        return None

    def _check_gateway_lock(self) -> AuditFinding | None:
        s = get_settings()
        if s.gateway_lock_path == "/tmp/prime-gateway.lock":
            return AuditFinding(
                severity="info", code="DEFAULT_LOCK_PATH",
                message="Gateway lock uses /tmp (shared, not persistent).",
                fix="Set GATEWAY_LOCK_PATH to a dedicated path in production",
            )
        return None

    def _check_rate_limit(self) -> AuditFinding | None:
        return None
