#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
BOTS_CONFIG = ROOT / "config" / "bots.yaml"
API_HEALTH_URL = os.getenv("PRIME_API_URL", "http://localhost:8000").rstrip("/") + "/api/healthz"

TELEGRAM_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")
LLM_PROVIDER_TYPES = {
    "OpenAI",
    "Anthropic",
    "DeepSeek",
    "Mistral",
    "Gemini",
    "Kimi",
    "Qwen",
    "GLM",
    "Ollama",
}

R = "\033[0m"
GRN = "\033[92m"
YLW = "\033[93m"
RED = "\033[91m"
BLD = "\033[1m"


def disable_color() -> None:
    global R, GRN, YLW, RED, BLD
    R = ""
    GRN = ""
    YLW = ""
    RED = ""
    BLD = ""


def ok(msg: str) -> None:
    print(f"{GRN}✓{R} {msg}")


def warn(msg: str) -> None:
    print(f"{YLW}!{R} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}✗{R} {msg}")


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def save_env_value(path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    replaced = False

    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                existing_key = stripped.split("=", 1)[0].strip()
                if existing_key == key:
                    lines.append(f"{key}={value}")
                    replaced = True
                    continue
            lines.append(raw)

    if not replaced:
        lines.append(f"{key}={value}")

    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def unique_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def mask_token(token: str) -> str:
    if len(token) <= 12:
        return token
    return f"{token[:6]}...{token[-4:]}"


def is_token_format_valid(token: str) -> bool:
    return bool(TELEGRAM_TOKEN_RE.match(token or ""))


def load_bots_yaml(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        import yaml  # type: ignore
    except Exception:
        return []
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    bots = parsed.get("bots")
    if isinstance(bots, list):
        return [row for row in bots if isinstance(row, dict)]
    return []


def get_telegram_snapshot() -> dict[str, Any]:
    env = load_env(ENV_FILE)
    tokens = parse_csv(env.get("TELEGRAM_BOT_TOKENS"))
    bots = load_bots_yaml(BOTS_CONFIG)

    configured_channels: set[str] = set()
    active_bots = 0
    telegram_bots = 0
    telegram_active_bots = 0
    for bot in bots:
        channels = bot.get("channels") or []
        normalized_channels: set[str] = set()
        if isinstance(channels, list):
            for channel in channels:
                if isinstance(channel, str):
                    c = channel.strip().lower()
                    if c:
                        configured_channels.add(c)
                        normalized_channels.add(c)

        is_active = bool(bot.get("active", True))
        if is_active:
            active_bots += 1

        if "telegram" in normalized_channels:
            telegram_bots += 1
            if is_active:
                telegram_active_bots += 1

    extra_channels = sorted(c for c in configured_channels if c != "telegram")
    return {
        "telegram": {
            "implemented": True,
            "enabled": len(tokens) > 0 or telegram_bots > 0,
            "token_count": len(tokens),
            "configured_bots": telegram_bots,
            "active_configured_bots": telegram_active_bots,
            "tokens_masked": [mask_token(t) for t in tokens[:3]],
        },
        "bots": {"count": len(bots), "active_count": active_bots},
        "extra_channels_in_yaml": extra_channels,
    }


def check_backend_health(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            if resp.status == 200:
                return True, "ok"
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


def telegram_get_me(token: str, timeout: float = 6.0) -> tuple[bool, str]:
    if not is_token_format_valid(token):
        return False, "Invalid token format"
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return False, "Non-JSON Telegram response"

    if not isinstance(payload, dict):
        return False, "Unexpected Telegram response"

    if not bool(payload.get("ok")):
        return False, str(payload.get("description") or "Telegram API error")

    result = payload.get("result") or {}
    username = result.get("username")
    first_name = result.get("first_name")
    bot_id = result.get("id")
    label = username or first_name or bot_id or "unknown_bot"
    return True, str(label)


def _extract_json_line(raw: str) -> dict[str, Any] | None:
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _backend_runtime_snapshot(timeout: float = 12.0) -> tuple[bool, dict[str, Any] | str]:
    script = r"""
import json
import sys
sys.path.insert(0, "/app")
from app.persistence.database import SessionLocal
from app.persistence.models import Agent, Binding, Bot, PairingRequest, PairingStatus, Provider

try:
    with SessionLocal() as db:
        bots = db.query(Bot).all()
        bindings = db.query(Binding).filter(Binding.channel == "telegram", Binding.active.is_(True)).all()
        agent_ids = {b.agent_id for b in bindings}

        data_bots = []
        for b in bots:
            data_bots.append({
                "id": str(b.id),
                "name": b.name,
                "active": bool(b.active),
                "channels": b.channels or [],
            })

        data_bindings = []
        for b in bindings:
            data_bindings.append({
                "id": str(b.id),
                "bot_id": str(b.bot_id),
                "agent_id": str(b.agent_id),
                "active": bool(b.active),
                "account_id": b.account_id,
                "peer": b.peer,
            })

        data_agents = []
        for aid in agent_ids:
            a = db.get(Agent, aid)
            if not a:
                continue
            provider = db.get(Provider, a.default_provider_id) if a.default_provider_id else None
            ptype = str(getattr(provider.type, "value", provider.type)) if provider else None
            cfg = dict(provider.config or {}) if provider else {}
            requires_key = bool(ptype in {"OpenAI", "Anthropic", "DeepSeek", "Mistral", "Gemini", "Kimi", "Qwen", "GLM"})
            has_key = bool(cfg.get("api_key")) if requires_key else True
            data_agents.append({
                "id": str(a.id),
                "name": a.name,
                "active": bool(a.active),
                "dm_policy": str(a.dm_policy),
                "provider_name": provider.name if provider else None,
                "provider_type": ptype,
                "provider_active": bool(provider.active) if provider else False,
                "provider_requires_key": requires_key,
                "provider_has_api_key": has_key,
            })

        pending_pairings = db.query(PairingRequest).filter(PairingRequest.status == PairingStatus.pending).count()

        print(json.dumps({
            "ok": True,
            "bots": data_bots,
            "bindings": data_bindings,
            "agents": data_agents,
            "pending_pairings": int(pending_pairings),
        }))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
"""
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "backend",
        "python",
        "-c",
        script,
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout)),
            check=False,
        )
    except Exception as exc:
        return False, str(exc)

    payload = _extract_json_line(result.stdout or "")
    if payload is not None:
        if payload.get("ok"):
            return True, payload
        return False, str(payload.get("error") or "runtime snapshot failed")

    text = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
    return False, text or "runtime snapshot failed"


def _backend_live_dry_run(timeout: float = 45.0) -> tuple[bool, dict[str, Any] | str]:
    script = r"""
import json
import sys
sys.path.insert(0, "/app")
from app.persistence.database import SessionLocal
from app.persistence.models import Agent, Binding, Provider
from app.services.agent_runner import AgentRunner

try:
    with SessionLocal() as db:
        binding = (
            db.query(Binding)
            .filter(Binding.channel == "telegram", Binding.active.is_(True))
            .order_by(Binding.priority.desc())
            .first()
        )
        if not binding:
            print(json.dumps({"ok": False, "error": "no active telegram binding"}))
            raise SystemExit(0)

        agent = db.get(Agent, binding.agent_id)
        if not agent or not agent.active:
            print(json.dumps({"ok": False, "error": "bound agent not found or inactive"}))
            raise SystemExit(0)

        provider = db.get(Provider, agent.default_provider_id) if agent.default_provider_id else None
        if not provider or not provider.active:
            print(json.dumps({"ok": False, "error": "default provider not found or inactive"}))
            raise SystemExit(0)

        ptype = str(getattr(provider.type, "value", provider.type))
        if ptype not in {"OpenAI", "Anthropic", "DeepSeek", "Mistral", "Gemini", "Kimi", "Qwen", "GLM", "Ollama"}:
            print(json.dumps({"ok": False, "error": f"provider type {ptype} is not supported for dry-run"}))
            raise SystemExit(0)

        cfg = dict(provider.config or {})
        if ptype in {"OpenAI", "Anthropic", "DeepSeek", "Mistral", "Gemini", "Kimi", "Qwen", "GLM"} and not cfg.get("api_key"):
            print(json.dumps({"ok": False, "error": f"provider {provider.name} has no api_key"}))
            raise SystemExit(0)

    runner = AgentRunner()
    result = runner.run_with_meta(
        "Reply with exactly: OK",
        provider_type=provider.type,
        provider_name=provider.name,
        provider_config=cfg,
        system=(agent.system_prompt or "You are a helpful assistant."),
        history=[],
        workspace_path=None,
        model=None,
        max_tokens=64,
    )
    text = (result.text or "").strip()
    print(json.dumps({
        "ok": True,
        "provider": provider.name,
        "provider_type": ptype,
        "model": result.model,
        "response_preview": text[:160],
    }))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
"""
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "backend",
        "python",
        "-c",
        script,
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=max(5.0, float(timeout)),
            check=False,
        )
    except Exception as exc:
        return False, str(exc)

    payload = _extract_json_line(result.stdout or "")
    if payload is not None:
        if payload.get("ok"):
            return True, payload
        return False, str(payload.get("error") or "dry-run failed")

    text = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
    return False, text or "dry-run failed"


def cmd_supported(args: argparse.Namespace) -> int:
    print(f"{BLD}Supported Channels{R}")
    print("- telegram: Implemented")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    snapshot = get_telegram_snapshot()
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=True, indent=2))
        return 0

    tg = snapshot["telegram"]
    print(f"{BLD}Prime Channels (Telegram-first){R}")
    print(f"Telegram enabled: {'yes' if tg['enabled'] else 'no'}")
    print(f"Telegram tokens:  {tg['token_count']}")
    print(f"Bots in config:   {snapshot['bots']['count']} (active: {snapshot['bots']['active_count']})")
    print(f"Bots w/telegram:  {tg['configured_bots']} (active: {tg['active_configured_bots']})")
    print("")
    if tg["enabled"]:
        ok("telegram: enabled")
    else:
        warn("telegram: disabled")

    masked = tg.get("tokens_masked") or []
    if masked:
        ok(f"Token sample: {', '.join(masked)}")

    extras = snapshot.get("extra_channels_in_yaml") or []
    if extras:
        warn(f"Non-telegram channels found in bots.yaml: {', '.join(extras)}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    snapshot = get_telegram_snapshot()
    backend_ok, backend_msg = check_backend_health(args.health_url)
    env = load_env(ENV_FILE)
    tokens = parse_csv(env.get("TELEGRAM_BOT_TOKENS"))

    all_ok = True
    if backend_ok:
        ok(f"Backend health: {args.health_url}")
    else:
        fail(f"Backend health: {backend_msg}")
        all_ok = False

    if snapshot["telegram"]["token_count"] > 0:
        ok("Telegram token is configured")
    else:
        fail("TELEGRAM_BOT_TOKENS is empty")
        all_ok = False

    tg_bots = int(snapshot["telegram"]["configured_bots"])
    if tg_bots > 0:
        ok(f"bots.yaml has telegram bots ({tg_bots})")
    else:
        warn("No telegram channels found in bots.yaml")

    extras = snapshot.get("extra_channels_in_yaml") or []
    if extras:
        warn(f"Extra non-telegram channels configured: {', '.join(extras)}")

    if args.verify_api and tokens:
        to_verify = tokens if args.all_tokens else tokens[:1]
        for idx, token in enumerate(to_verify, 1):
            valid, detail = telegram_get_me(token, timeout=args.timeout)
            if valid:
                ok(f"Token {idx} verified via getMe: {detail}")
            else:
                fail(f"Token {idx} verification failed: {detail}")
                all_ok = False

    if all_ok:
        ok("Channel doctor checks passed")
        return 0
    return 1


def cmd_live(args: argparse.Namespace) -> int:
    print(f"{BLD}Prime Telegram Live Doctor{R}")
    base_ok = cmd_doctor(
        argparse.Namespace(
            health_url=args.health_url,
            timeout=args.timeout,
            verify_api=args.verify_api,
            all_tokens=args.all_tokens,
        )
    ) == 0
    all_ok = base_ok

    ok_snapshot, payload = _backend_runtime_snapshot(timeout=args.runtime_timeout)
    if not ok_snapshot:
        fail(f"Runtime snapshot failed: {payload}")
        return 1

    snapshot = payload if isinstance(payload, dict) else {}
    print("")
    print(f"{BLD}Runtime checks{R}")

    bots = snapshot.get("bots") or []
    tg_active = [
        b for b in bots
        if b.get("active") and "telegram" in [str(c).lower() for c in (b.get("channels") or [])]
    ]
    if tg_active:
        ok(f"Active telegram bots in DB: {len(tg_active)}")
    else:
        fail("No active telegram bots in DB")
        all_ok = False

    bindings = snapshot.get("bindings") or []
    if bindings:
        ok(f"Active telegram bindings: {len(bindings)}")
    else:
        fail("No active telegram bindings in DB")
        all_ok = False

    agents = snapshot.get("agents") or []
    if agents:
        for agent in agents:
            name = str(agent.get("name") or "unknown_agent")
            dm_policy = str(agent.get("dm_policy") or "unknown")
            provider_name = str(agent.get("provider_name") or "none")
            provider_active = bool(agent.get("provider_active"))
            requires_key = bool(agent.get("provider_requires_key"))
            has_key = bool(agent.get("provider_has_api_key"))
            if provider_name == "none":
                fail(f"Agent {name}: default provider is not set")
                all_ok = False
                continue
            if not provider_active:
                fail(f"Agent {name}: provider {provider_name} is inactive")
                all_ok = False
                continue
            if requires_key and not has_key:
                fail(f"Agent {name}: provider {provider_name} has no api_key")
                all_ok = False
                continue
            ok(f"Agent {name}: dm_policy={dm_policy}, provider={provider_name}")
    else:
        fail("No agents connected to telegram bindings")
        all_ok = False

    pending_pairings = int(snapshot.get("pending_pairings") or 0)
    if pending_pairings > 0:
        warn(f"Pending pairing requests: {pending_pairings}")
    else:
        ok("No pending pairing requests")

    if args.send_test:
        print("")
        ok_test, test_payload = _backend_live_dry_run(timeout=args.run_timeout)
        if ok_test and isinstance(test_payload, dict):
            ok(
                "Dry-run prompt OK via "
                f"{test_payload.get('provider')} ({test_payload.get('model')})"
            )
        else:
            fail(f"Dry-run prompt failed: {test_payload}")
            all_ok = False

    return 0 if all_ok else 1


def cmd_connect(args: argparse.Namespace) -> int:
    env = load_env(ENV_FILE)
    existing = parse_csv(env.get("TELEGRAM_BOT_TOKENS"))

    token = (args.token or "").strip()
    if not token:
        token = input("Telegram bot token: ").strip()
    if not token:
        fail("Token is required")
        return 1
    if not is_token_format_valid(token):
        fail("Invalid token format. Expected <digits>:<secret>")
        return 1

    tokens = unique_keep_order([*existing, token]) if args.append else [token]
    save_env_value(ENV_FILE, "TELEGRAM_BOT_TOKENS", ",".join(tokens))
    ok(f"Saved TELEGRAM_BOT_TOKENS ({len(tokens)} token(s)) to {ENV_FILE}")

    if args.verify:
        valid, detail = telegram_get_me(token, timeout=args.timeout)
        if valid:
            ok(f"Verified token via getMe: {detail}")
        else:
            fail(f"Token verify failed: {detail}")
            return 1

    print("Next step: prime gateway restart backend")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    env = load_env(ENV_FILE)
    configured = parse_csv(env.get("TELEGRAM_BOT_TOKENS"))

    if args.token:
        tokens = [args.token.strip()]
    else:
        tokens = configured if args.all else configured[:1]

    if not tokens:
        fail("No token to verify. Use 'prime channels connect --token <TOKEN>' first.")
        return 1

    all_ok = True
    for idx, token in enumerate(tokens, 1):
        valid, detail = telegram_get_me(token, timeout=args.timeout)
        if valid:
            ok(f"Token {idx} OK: {detail}")
        else:
            fail(f"Token {idx} failed: {detail}")
            all_ok = False
    return 0 if all_ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prime channels (Telegram-first)")
    parser.add_argument("--health-url", default=API_HEALTH_URL)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_supported = sub.add_parser("supported", help="Show supported channels")
    p_supported.set_defaults(func=cmd_supported)

    p_list = sub.add_parser("list", help="Show Telegram channel status")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_doctor = sub.add_parser("doctor", help="Run Telegram channel health checks")
    p_doctor.add_argument("--verify-api", action="store_true", help="Verify token(s) with Telegram getMe API")
    p_doctor.add_argument("--all-tokens", action="store_true", help="Verify all configured tokens")
    p_doctor.set_defaults(func=cmd_doctor)

    p_live = sub.add_parser("live", help="Run deep Telegram runtime diagnostics")
    p_live.add_argument(
        "--verify-api",
        dest="verify_api",
        action="store_true",
        help="Verify token(s) with Telegram getMe API (default: on)",
    )
    p_live.add_argument(
        "--no-verify-api",
        dest="verify_api",
        action="store_false",
        help="Skip Telegram getMe verification",
    )
    p_live.add_argument("--all-tokens", action="store_true", help="Verify all configured tokens")
    p_live.add_argument("--send-test", action="store_true", help="Send a real dry-run prompt to the selected provider")
    p_live.add_argument("--runtime-timeout", type=float, default=12.0, help="Runtime snapshot timeout in seconds")
    p_live.add_argument("--run-timeout", type=float, default=45.0, help="Dry-run timeout in seconds")
    p_live.set_defaults(func=cmd_live, verify_api=True)

    p_connect = sub.add_parser("connect", help="Set Telegram token in .env")
    p_connect.add_argument("--token", help="Telegram bot token")
    p_connect.add_argument("--append", action="store_true", help="Append token instead of replacing existing")
    p_connect.add_argument("--verify", action="store_true", help="Verify token with Telegram getMe API")
    p_connect.set_defaults(func=cmd_connect)

    p_verify = sub.add_parser("verify", help="Verify Telegram token(s) with getMe API")
    p_verify.add_argument("--token", help="Verify specific token instead of .env")
    p_verify.add_argument("--all", action="store_true", help="Verify all tokens from .env")
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.no_color or not sys.stdout.isatty():
        disable_color()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
