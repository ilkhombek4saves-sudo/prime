#!/usr/bin/env python3
"""
Prime Router v2 — Fast Local Routing + API Execution
No intermediate LLM calls for preprocessing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import List, Tuple

WORKSPACE = Path(os.environ.get("PRIME_WORKSPACE", os.getcwd()))

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


class FastRouter:
    """Fast rule-based router without LLM preprocessing"""
    
    LOCAL_MODEL = "qwen2.5:7b"  # Faster on CPU
    
    def __init__(self):
        self.workspace = WORKSPACE
    
    def analyze_and_route(self, query: str) -> Tuple[str, List[str], str]:
        """
        Returns: (routing_decision, providers, prepared_context)
        Decision: local/simple/complex/code/arch/critical/direct
        """
        print(f"\n{BOLD}{CYN}══════ PRIME ROUTER ══════{R}")
        
        q_lower = query.lower()
        context_parts = []
        
        # 0. FAST PATH: Direct execution for simple commands (no LLM)
        if any(kw in q_lower for kw in ["ls ", "dir ", "list files", "what files", "show files"]):
            log("Fast path: direct directory listing")
            return "direct", [], self._list_directory()
        
        # 1. Check for directory listing request (with LLM analysis)
        dir_keywords = ["directory", "what's in", "what is in", "files in"]
        if any(kw in q_lower for kw in dir_keywords):
            log("Detected directory listing request")
            dir_listing = self._list_directory()
            context_parts.append(f"=== DIRECTORY LISTING ===\n{dir_listing}")
        
        # 2. Extract and read specific files
        files = self._extract_files(query)
        for f in files[:3]:
            content = self._read_file(f)
            if content:
                context_parts.append(f"=== {f} ===\n{content[:1500]}")
        
        # 3. Rule-based complexity detection
        decision = self._classify(query)
        
        # 4. Select providers
        providers = self._select_providers(decision)
        
        # 5. Prepare final context
        file_context = "\n\n".join(context_parts) or "(no specific files or directories requested)"
        
        context = f"""Query: {query}

Workspace: {self.workspace}

Context:
{file_context}

Git context:
{self._get_git_context()}"""
        
        log(f"Decision: {decision}")
        log(f"Providers: {', '.join(providers)}")
        
        return decision, providers, context
    
    def _list_directory(self) -> str:
        """List files in workspace directory"""
        try:
            result = subprocess.run(
                f"ls -la {self.workspace}",
                shell=True, capture_output=True, text=True, timeout=10
            )
            return result.stdout[:3000]  # Limit output
        except Exception as e:
            return f"Error listing directory: {e}"
    
    def _classify(self, query: str) -> str:
        """Rule-based classification (no LLM)"""
        q = query.lower()
        
        # CRITICAL: High stakes
        critical_keywords = ["production", "deploy", "security", "password", "secret", "token", "critical"]
        if any(kw in q for kw in critical_keywords):
            return "critical"
        
        # ARCH: Architecture decisions
        arch_keywords = ["architecture", "refactor", "design pattern", "structure", "system design"]
        if any(kw in q for kw in arch_keywords):
            return "arch"
        
        # CODE: Code generation
        code_keywords = ["write function", "implement", "generate code", "create class", "code:"]
        if any(kw in q for kw in code_keywords):
            return "code"
        
        # COMPLEX: Reasoning needed
        complex_keywords = ["why", "how to", "explain", "analyze", "compare", "debug", "fix"]
        if any(kw in q for kw in complex_keywords):
            return "complex"
        
        # SIMPLE: Direct file read or simple question
        simple_keywords = ["read", "show", "what is", "list", "cat "]
        if any(kw in q for kw in simple_keywords) or len(query) < 50:
            return "simple"
        
        # Default: local processing
        return "local"
    
    def _select_providers(self, decision: str) -> List[str]:
        """Select API providers based on decision"""
        if decision == "local":
            return ["local"]
        
        if decision == "simple":
            return ["local"]
        
        if decision == "complex":
            # First available
            if os.environ.get("OPENAI_API_KEY"): return ["openai"]
            if os.environ.get("ANTHROPIC_API_KEY"): return ["anthropic"]
            return ["local"]
        
        if decision == "code":
            # Priority: Claude > Gemini > DeepSeek
            providers = []
            if os.environ.get("ANTHROPIC_API_KEY"): providers.append("anthropic")
            if os.environ.get("GEMINI_API_KEY"): providers.append("gemini")
            if os.environ.get("DEEPSEEK_API_KEY"): providers.append("deepseek")
            if os.environ.get("OPENAI_API_KEY"): providers.append("openai")
            return providers[:2] if providers else ["local"]
        
        if decision == "arch":
            # Ensemble
            providers = []
            if os.environ.get("ANTHROPIC_API_KEY"): providers.append("anthropic")
            if os.environ.get("GEMINI_API_KEY"): providers.append("gemini")
            if os.environ.get("DEEPSEEK_API_KEY"): providers.append("deepseek")
            return providers if providers else ["local"]
        
        if decision == "critical":
            if os.environ.get("ANTHROPIC_API_KEY"): return ["anthropic"]
            if os.environ.get("OPENAI_API_KEY"): return ["openai"]
            return ["local"]
        
        return ["local"]
    
    def execute(self, decision: str, providers: List[str], context: str) -> str:
        """Execute on selected providers"""
        print(f"\n{BOLD}{CYN}══════ EXECUTION ══════{R}")
        
        # Direct output (no LLM)
        if decision == "direct":
            print(f"\n{BOLD}{GRN}Response:{R}\n{context}\n")
            return context
        
        if decision in ["local", "simple"]:
            return self._execute_local(context)
        
        if len(providers) == 1:
            return self._execute_api(providers[0], context)
        
        # Ensemble
        results = []
        for provider in providers:
            result = self._execute_api(provider, context)
            results.append(f"=== {provider.upper()} ===\n{result}")
        
        # Synthesize locally
        return self._execute_local("\n\n".join(results) + "\n\nSynthesize the above responses:")
    
    def _execute_local(self, context: str) -> str:
        """Execute on local Qwen"""
        log("Local Qwen2.5-14B processing...")
        
        try:
            req_data = {
                "model": self.LOCAL_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant. Be concise."},
                    {"role": "user", "content": context}
                ],
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 2000}
            }
            
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=json.dumps(req_data).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read().decode())
                return data["message"]["content"]
        except Exception as e:
            return f"Local error: {e}"
    
    def _execute_api(self, provider: str, context: str) -> str:
        """Execute on cloud API"""
        log(f"API: {provider}")
        
        try:
            import httpx
            
            if provider == "openai":
                key = os.environ.get("OPENAI_API_KEY")
                if not key: return "Error: OPENAI_API_KEY not set"
                resp = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": context}], "temperature": 0.7},
                    timeout=60
                )
                return resp.json()["choices"][0]["message"]["content"]
            
            elif provider == "anthropic":
                key = os.environ.get("ANTHROPIC_API_KEY")
                if not key: return "Error: ANTHROPIC_API_KEY not set"
                resp = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                    json={"model": "claude-3-5-sonnet-20241022", "max_tokens": 4096, "messages": [{"role": "user", "content": context}]},
                    timeout=60
                )
                return resp.json()["content"][0]["text"]
            
            elif provider == "gemini":
                key = os.environ.get("GEMINI_API_KEY")
                if not key: return "Error: GEMINI_API_KEY not set"
                resp = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
                    json={"contents": [{"parts": [{"text": context}]}]},
                    timeout=60
                )
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            
            elif provider == "deepseek":
                key = os.environ.get("DEEPSEEK_API_KEY")
                if not key: return "Error: DEEPSEEK_API_KEY not set"
                resp = httpx.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": context}]},
                    timeout=60
                )
                return resp.json()["choices"][0]["message"]["content"]
            
            elif provider == "kimi":
                key = os.environ.get("KIMI_API_KEY")
                if not key: return "Error: KIMI_API_KEY not set"
                resp = httpx.post(
                    "https://api.moonshot.cn/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": "moonshot-v1-8k", "messages": [{"role": "user", "content": context}]},
                    timeout=60
                )
                return resp.json()["choices"][0]["message"]["content"]
            
        except Exception as e:
            return f"{provider} error: {e}"
    
    def _extract_files(self, query: str) -> List[str]:
        """Extract file mentions"""
        pattern = r'[\'"]?([\w\-./]+\.(?:py|js|ts|jsx|tsx|json|md|yaml|yml|toml|rs|go|java|cpp|c|h))[\'"]?' 
        return list(set(re.findall(pattern, query, re.IGNORECASE)))
    
    def _read_file(self, path: str) -> str:
        """Read file"""
        try:
            p = self.workspace / path
            if p.exists() and p.is_file():
                return p.read_text(encoding='utf-8', errors='ignore')
        except:
            pass
        return ""
    
    def _get_git_context(self) -> str:
        """Get git context"""
        try:
            r = subprocess.run(f"cd {self.workspace} && git log --oneline -3 2>/dev/null", shell=True, capture_output=True, text=True)
            return r.stdout.strip()
        except:
            return ""


def main():
    parser = argparse.ArgumentParser(prog="prime", description="Prime Router v2")
    parser.add_argument("query", nargs="?", default="", help="Query to process")
    
    args = parser.parse_args()
    
    if not args.query:
        # Interactive mode
        print(f"{BOLD}{CYN}Prime Router v2 — Type 'exit' to quit{R}\n")
        while True:
            try:
                query = input(f"{CYN}>>{R} ")
                if query.lower() in ["exit", "quit"]:
                    break
                if not query.strip():
                    continue
                
                router = FastRouter()
                decision, providers, context = router.analyze_and_route(query)
                response = router.execute(decision, providers, context)
                
                print(f"\n{BOLD}{GRN}Response:{R}\n{response}\n")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"{RED}Error: {e}{R}")
    else:
        router = FastRouter()
        decision, providers, context = router.analyze_and_route(args.query)
        response = router.execute(decision, providers, context)
        
        print(f"\n{BOLD}{GRN}Response:{R}\n{response}\n")


if __name__ == "__main__":
    main()
