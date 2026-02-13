#!/usr/bin/env python3
"""
Prime Lite v2 — Enhanced AI Agent Platform
- Recursive project discovery
- Fuzzy file search
- API resilience with retry + fallback
- Self-aware configuration tracking
- Compatible with OpenClaw.ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple

# Import new modules
from resilience import APIExecutor, ConnectivityChecker, ResultCache
from scanner import ProjectScanner, FileFinder
from selfaware import PrimeSelfAware

WORKSPACE = Path(os.environ.get("PRIME_WORKSPACE", os.getcwd()))
CONFIG_DIR = Path.home() / ".config" / "prime"

R = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
CYN = "\033[96m"


def log(msg): print(f"  {BLU}→{R} {msg}")
def ok(msg): print(f"  {GRN}✓{R} {msg}")
def warn(msg): print(f"  {YLW}!{R} {msg}")
def error(msg): print(f"  {RED}✗{R} {msg}", file=sys.stderr)


class PrimeRouter:
    """Main router with all improvements"""

    def __init__(self):
        self.workspace = WORKSPACE
        self.scanner = ProjectScanner(max_depth=10)
        self.finder = FileFinder(self.workspace)
        self.executor = APIExecutor(max_retries=3, base_delay=1.0)
        self.self_aware = PrimeSelfAware()
        self.connectivity = ConnectivityChecker()

    def analyze_and_route(self, query: str) -> Tuple[str, List[str], str]:
        """
        Enhanced routing with:
        - Recursive project scanning
        - Fuzzy file finding
        - Smart complexity detection
        """
        print(f"\n{BOLD}{CYN}══════ PRIME ROUTER v2 ══════{R}")

        q_lower = query.lower()
        context_parts = []

        # ============================================================================
        # FAST PATHS - No LLM needed
        # ============================================================================

        # 1. Project discovery
        if any(kw in q_lower for kw in ["projects", "проекты", "what projects", "какие проекты", "scan"]):
            log("Fast path: recursive project scanning")
            projects = self.scanner.scan(self.workspace)
            output = self._format_projects(projects)
            return "direct", [], output

        # 2. Directory listing
        if any(kw in q_lower for kw in ["ls ", "dir ", "list files", "what files", "show files"]):
            log("Fast path: directory listing")
            return "direct", [], self.finder.list_directory()

        # 3. File reading
        import re
        read_match = re.search(r'(?:read|show|cat|open)\s+[\'"]?([\w\-./]+\.[\w]+)[\'"]?', query, re.IGNORECASE)
        if read_match:
            fname = read_match.group(1)
            content = self.finder.read_file(fname)
            if content:
                log(f"Fast path: reading {fname}")
                return "direct", [], f"=== {fname} ===\n{content[:5000]}\n{'...[truncated]' if len(content) > 5000 else ''}"

        # ============================================================================
        # CONTEXT GATHERING - Using new intelligent finders
        # ============================================================================

        # Extract and read files
        log("Finding files mentioned in query...")
        files = self.finder.find_files(query)
        for name, path in files[:3]:
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')
                context_parts.append(f"=== {name} ===\n{content[:1500]}")
            except:
                pass

        # ============================================================================
        # ROUTING DECISION
        # ============================================================================

        decision = self._classify(query)
        providers = self._select_providers(decision)

        # Prepare context
        file_context = "\n\n".join(context_parts) or "(no files found)"
        context = f"""Query: {query}

Workspace: {self.workspace}

Files:
{file_context}

Git context:
{self._get_git_context()}"""

        log(f"Decision: {decision}")
        log(f"Providers: {', '.join(providers)}")

        return decision, providers, context

    def execute(self, decision: str, providers: List[str], context: str) -> str:
        """Execute with resilience and fallback"""
        print(f"\n{BOLD}{CYN}══════ EXECUTION ══════{R}")

        # Direct output (no LLM)
        if decision == "direct":
            return context

        if decision in ["local", "simple"]:
            return self._execute_with_resilience("local", context)

        if len(providers) == 1:
            return self._execute_with_resilience(providers[0], context)

        # Ensemble: try multiple providers
        results = []
        for provider in providers:
            success, result = self.executor.execute_with_fallback(provider, context)
            if success:
                results.append(f"=== {provider.upper()} ===\n{result}")
                break  # Use first successful response
            else:
                warn(f"{provider} failed: {result[:50]}")

        if results:
            return "\n\n".join(results)

        # All failed, fallback to local
        warn("All providers failed, using local Ollama...")
        success, result = self.executor.execute_with_fallback("local", context)
        return result if success else "Error: Could not process query"

    def _execute_with_resilience(self, provider: str, context: str) -> str:
        """Execute single provider with resilience"""
        success, result = self.executor.execute_with_fallback(provider, context)
        return result

    def _classify(self, query: str) -> str:
        """Rule-based classification"""
        q = query.lower()

        critical_keywords = ["production", "deploy", "security", "password", "secret", "token"]
        if any(kw in q for kw in critical_keywords):
            return "critical"

        arch_keywords = ["architecture", "refactor", "design", "structure"]
        if any(kw in q for kw in arch_keywords):
            return "arch"

        code_keywords = ["write", "implement", "generate", "create", "code:"]
        if any(kw in q for kw in code_keywords):
            return "code"

        complex_keywords = ["why", "how", "explain", "analyze", "debug", "fix"]
        if any(kw in q for kw in complex_keywords):
            return "complex"

        return "local"

    def _select_providers(self, decision: str) -> List[str]:
        """Select providers with availability check"""
        providers = []

        if decision == "local":
            return ["local"]

        if decision == "simple":
            return ["local"]

        if decision == "complex":
            # Try API with fallback
            if os.environ.get("OPENAI_API_KEY"):
                providers.append("openai")
            if os.environ.get("ANTHROPIC_API_KEY"):
                providers.append("anthropic")
            return providers if providers else ["local"]

        if decision == "code":
            # Priority: Claude > Gemini > DeepSeek
            if os.environ.get("ANTHROPIC_API_KEY"):
                providers.append("anthropic")
            if os.environ.get("GEMINI_API_KEY"):
                providers.append("gemini")
            if os.environ.get("DEEPSEEK_API_KEY"):
                providers.append("deepseek")
            if os.environ.get("OPENAI_API_KEY"):
                providers.append("openai")
            return providers[:2] if providers else ["local"]

        if decision == "arch":
            if os.environ.get("ANTHROPIC_API_KEY"):
                providers.append("anthropic")
            if os.environ.get("GEMINI_API_KEY"):
                providers.append("gemini")
            return providers if providers else ["local"]

        if decision == "critical":
            if os.environ.get("ANTHROPIC_API_KEY"):
                providers.append("anthropic")
            if os.environ.get("OPENAI_API_KEY"):
                providers.append("openai")
            return providers if providers else ["local"]

        return ["local"]

    def _get_git_context(self) -> str:
        """Get git info"""
        import subprocess
        try:
            result = subprocess.run(
                f"cd {self.workspace} && git log --oneline -3 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() or "(not a git repo)"
        except:
            return "(git unavailable)"

    def _format_projects(self, projects: List[dict]) -> str:
        """Format project list"""
        if not projects:
            return "No projects found in workspace"

        lines = [f"📁 Found {len(projects)} project(s):\n"]
        for p in projects[:20]:
            lines.append(f"  {p['name']} ({p['type']}) @ {p['path']}")
            if p.get('git_branch'):
                lines.append(f"    Branch: {p['git_branch']}")

        return "\n".join(lines)


# ============================================================================
# COMMANDS
# ============================================================================

def cmd_whoami():
    """Show Prime self-awareness"""
    self_aware = PrimeSelfAware()
    print(self_aware.whoami())


def cmd_status():
    """Show system status"""
    print(f"\n{BOLD}{CYN}══════ PRIME STATUS ══════{R}\n")

    self_aware = PrimeSelfAware()
    executor = APIExecutor()

    # Show self-awareness
    print(self_aware.whoami())

    # Check API availability
    print(f"{BOLD}{CYN}Checking API availability...{R}\n")

    providers = ["openai", "anthropic", "gemini", "deepseek", "kimi", "local"]
    for provider in providers:
        status = executor.check_provider_availability(provider)
        self_aware.update_api_status(provider, status.get("available", False), status.get("has_key", False))


def cmd_init():
    """Initialize Prime"""
    print(f"\n{BOLD}{CYN}══════ PRIME INIT ══════{R}\n")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ok(f"Config directory: {CONFIG_DIR}")

    env_file = CONFIG_DIR / ".env"
    if not env_file.exists():
        env_content = """# Prime Environment
# Add your API keys here:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GEMINI_API_KEY=...
# DEEPSEEK_API_KEY=sk-...
# KIMI_API_KEY=sk-...
"""
        env_file.write_text(env_content)
        env_file.chmod(0o600)
        ok(f"Created .env: {env_file}")

    # Initialize self-aware config
    self_aware = PrimeSelfAware()
    ok("Self-aware configuration initialized")

    print(f"\n{BOLD}{GRN}Prime initialized!{R}\n")


def cmd_scan():
    """Scan workspace for projects"""
    print(f"\n{BOLD}{CYN}══════ PROJECT SCANNER ══════{R}\n")

    scanner = ProjectScanner(max_depth=10)
    projects = scanner.scan(WORKSPACE)

    if not projects:
        warn("No projects found")
        return

    ok(f"Found {len(projects)} projects:\n")
    for p in sorted(projects, key=lambda x: x['depth']):
        indent = "  " * p['depth']
        print(f"{indent}📁 {p['name']} ({p['type']})")
        if p.get('git_branch'):
            print(f"{indent}   Branch: {p['git_branch']}")


def cmd_index():
    """Build file index"""
    print(f"\n{BOLD}{CYN}══════ FILE INDEXER ══════{R}\n")

    finder = FileFinder(WORKSPACE)
    count = finder.indexer.build_index(WORKSPACE)
    ok(f"Indexed {count} files")


def main():
    parser = argparse.ArgumentParser(prog="prime", description="Prime AI Agent v2")
    parser.add_argument("query", nargs="?", default="", help="Query to process")

    args = parser.parse_args()

    # Commands
    if args.query == "whoami":
        cmd_whoami()
        return

    if args.query == "status":
        cmd_status()
        return

    if args.query == "init":
        cmd_init()
        return

    if args.query == "scan":
        cmd_scan()
        return

    if args.query == "index":
        cmd_index()
        return

    if args.query == "help":
        parser.print_help()
        print(f"\n{BOLD}Commands:{R}")
        print("  prime whoami       Show Prime identity and deployment info")
        print("  prime status       Check system status and API availability")
        print("  prime init         Initialize Prime")
        print("  prime scan         Scan for projects (recursive)")
        print("  prime index        Build file index for fast search")
        print("  prime <query>      Send query to AI agent")
        return

    if not args.query:
        # Interactive mode
        print(f"{BOLD}{CYN}Prime Lite v2 — Type 'exit' to quit{R}\n")
        while True:
            try:
                query = input(f"{CYN}>>{R} ")
                if query.lower() in ["exit", "quit"]:
                    break
                if not query.strip():
                    continue

                router = PrimeRouter()
                decision, providers, context = router.analyze_and_route(query)
                response = router.execute(decision, providers, context)
                print(f"\n{BOLD}{GRN}Response:{R}\n{response}\n")

            except KeyboardInterrupt:
                break
            except Exception as e:
                error(f"Error: {e}")

    else:
        # Process single query
        router = PrimeRouter()
        decision, providers, context = router.analyze_and_route(args.query)
        response = router.execute(decision, providers, context)
        print(f"\n{BOLD}{GRN}Response:{R}\n{response}\n")


if __name__ == "__main__":
    main()
