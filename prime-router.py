#!/usr/bin/env python3
"""
Prime Router — Multi-tier LLM Architecture
Local Qwen2.5-14B: preprocessing | API: complex reasoning only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from enum import Enum

PRIME_HOME = Path(os.environ.get("PRIME_HOME", Path.home() / ".prime"))
CONFIG_DIR = Path.home() / ".config" / "prime"
WORKSPACE = Path(os.environ.get("PRIME_WORKSPACE", os.getcwd()))

R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
CYN = "\033[96m"


def log(msg): print(f"  {BLU}→{R} {msg}")
def ok(msg): print(f"  {GRN}✓{R} {msg}")
def warn(msg): print(f"  {YLW}!{R} {msg}")
def error(msg): print(f"  {RED}✗{R} {msg}", file=sys.stderr)
def step(n, msg): print(f"\n{BOLD}{CYN}[{n}/5]{R} {msg}")


class TaskType(Enum):
    SIMPLE = "simple"           # Local only
    ANALYSIS = "analysis"       # Local draft → API summary
    CODE = "code"               # Local context → API generation
    ARCHITECTURE = "arch"       # Local prep → multi-API ensemble
    CRITICAL = "critical"       # Direct to best API


@dataclass
class Context:
    raw_query: str
    workspace: Path
    files: List[str]
    git_context: str
    memory: str
    complexity: float  # 0-1
    needs_code: bool
    needs_architecture: bool


class LocalPreprocessor:
    """Tier 1: Qwen2.5-14B for all preprocessing"""
    
    MODEL = "qwen2.5:14b"
    
    def __init__(self):
        self.workspace = WORKSPACE
    
    def draft_analysis(self, query: str) -> Dict:
        """Step 1: Черновой анализ запроса"""
        step(1, "Draft Analysis (Local)")
        
        # Extract file mentions
        files = self._extract_files(query)
        log(f"Files mentioned: {files}")
        
        # Read mentioned files
        file_contents = {}
        for f in files[:5]:  # Limit to 5 files
            content = self._read_file(f)
            if content:
                file_contents[f] = content[:2000]  # First 2000 chars
        
        # Git context
        git_ctx = self._get_git_context()
        
        # Build draft
        draft = {
            "query": query,
            "files_found": list(file_contents.keys()),
            "file_previews": file_contents,
            "git_context": git_ctx,
            "workspace": str(self.workspace)
        }
        
        ok(f"Analyzed {len(file_contents)} files")
        return draft
    
    def summarize(self, draft: Dict) -> str:
        """Step 2: Суммаризация контекста"""
        step(2, "Summarization (Local)")
        
        summary_parts = []
        
        # Summarize files
        for fname, content in draft["file_previews"].items():
            log(f"Summarizing {fname}...")
            prompt = f"""Summarize this code file in 2-3 sentences. Focus on purpose and key functions.

File: {fname}
Content (first 2000 chars):
{content[:1500]}

Summary:"""
            
            summary = self._call_local(prompt, max_tokens=100)
            summary_parts.append(f"{fname}: {summary}")
        
        result = "\n".join(summary_parts)
        ok(f"Generated {len(summary_parts)} summaries")
        return result
    
    def clean_prompt(self, query: str, summaries: str) -> str:
        """Step 3: Очистка промпта"""
        step(3, "Prompt Cleaning (Local)")
        
        prompt = f"""Clean and optimize this user query for an AI assistant.
Remove fluff, clarify intent, and format concisely.

Original: {query}

Context from files:
{summaries}

Cleaned query:"""
        
        cleaned = self._call_local(prompt, max_tokens=150)
        log(f"Cleaned: {cleaned[:100]}...")
        return cleaned
    
    def prepare_context(self, cleaned_query: str, draft: Dict) -> Context:
        """Step 4: Подготовка контекста для роутера"""
        step(4, "Context Preparation (Local)")
        
        # Analyze complexity
        complexity = self._analyze_complexity(cleaned_query)
        log(f"Complexity score: {complexity:.2f}")
        
        # Detect code needs
        needs_code = any(kw in cleaned_query.lower() for kw in [
            "code", "function", "class", "implement", "write", "generate",
            "код", "функция", "класс", "реализуй", "напиши"
        ])
        
        # Detect architecture needs
        needs_arch = any(kw in cleaned_query.lower() for kw in [
            "architecture", "design", "structure", "refactor", "pattern",
            "архитектура", "дизайн", "структура", "рефакторинг"
        ])
        
        ctx = Context(
            raw_query=draft["query"],
            workspace=self.workspace,
            files=draft["files_found"],
            git_context=draft["git_context"],
            memory=self._load_memory(),
            complexity=complexity,
            needs_code=needs_code,
            needs_architecture=needs_arch
        )
        
        ok(f"Context ready: complexity={complexity:.2f}, code={needs_code}, arch={needs_arch}")
        return ctx
    
    def route(self, ctx: Context, cleaned_query: str) -> Tuple[TaskType, List[str]]:
        """Step 5: Решение — куда отправлять"""
        step(5, "Routing Decision (Local)")
        
        prompt = f"""You are a router. Decide where to send this query based on complexity and type.

Query: {cleaned_query}
Complexity: {ctx.complexity:.2f}/1.0
Needs code: {ctx.needs_code}
Needs architecture: {ctx.needs_architecture}

Decide:
1. simple — Can answer locally (simple questions, file reads)
2. analysis — Needs API for reasoning (complex analysis, debugging)
3. code — Needs API for code generation
4. arch — Needs multi-model architecture review
5. critical — High stakes, needs best model

Respond with ONLY one word: simple/analysis/code/arch/critical"""
        
        decision = self._call_local(prompt, max_tokens=20).strip().lower()
        
        # Map to TaskType
        task_map = {
            "simple": TaskType.SIMPLE,
            "analysis": TaskType.ANALYSIS,
            "code": TaskType.CODE,
            "arch": TaskType.ARCHITECTURE,
            "critical": TaskType.CRITICAL
        }
        
        task_type = task_map.get(decision, TaskType.SIMPLE)
        
        # Select providers
        providers = self._select_providers(task_type, ctx)
        
        log(f"Decision: {task_type.value}")
        log(f"Providers: {', '.join(providers)}")
        
        return task_type, providers
    
    def _select_providers(self, task_type: TaskType, ctx: Context) -> List[str]:
        """Select API providers based on task"""
        if task_type == TaskType.SIMPLE:
            return ["local"]
        
        elif task_type == TaskType.ANALYSIS:
            return ["openai", "anthropic"]
        
        elif task_type == TaskType.CODE:
            # Priority: Claude > Gemini > DeepSeek > others
            available = []
            if os.environ.get("ANTHROPIC_API_KEY"):
                available.append("anthropic")
            if os.environ.get("GEMINI_API_KEY"):
                available.append("gemini")
            if os.environ.get("DEEPSEEK_API_KEY"):
                available.append("deepseek")
            if os.environ.get("OPENAI_API_KEY"):
                available.append("openai")
            if os.environ.get("KIMI_API_KEY"):
                available.append("kimi")
            
            return available[:2] if available else ["local"]
        
        elif task_type == TaskType.ARCHITECTURE:
            # Ensemble approach
            return ["anthropic", "gemini", "deepseek"]
        
        elif task_type == TaskType.CRITICAL:
            return ["anthropic"]  # Best for critical tasks
        
        return ["local"]
    
    def _call_local(self, prompt: str, max_tokens: int = 200) -> str:
        """Call local Qwen2.5-14B"""
        try:
            req_data = {
                "model": self.MODEL,
                "messages": [
                    {"role": "system", "content": "You are a fast preprocessing assistant. Be concise."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": max_tokens
                }
            }
            
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=json.dumps(req_data).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode())
                return data["message"]["content"]
        except Exception as e:
            warn(f"Local LLM error: {e}")
            return ""
    
    def _extract_files(self, query: str) -> List[str]:
        """Extract file mentions from query"""
        patterns = [
            r'[\'"]([\w\-./]+\.(?:py|js|ts|json|md|yaml|yml|toml))[\'"]',
            r'\b([\w\-./]+\.(?:py|js|ts|json|md|yaml|yml|toml))\b'
        ]
        
        files = set()
        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            files.update(matches)
        
        return list(files)
    
    def _read_file(self, path: str) -> Optional[str]:
        """Read file content"""
        try:
            p = self.workspace / path
            if p.exists() and p.is_file():
                return p.read_text(encoding='utf-8', errors='ignore')
        except:
            pass
        return None
    
    def _get_git_context(self) -> str:
        """Get recent git commits"""
        try:
            result = subprocess.run(
                f"cd {self.workspace} && git log --oneline -5 2>/dev/null",
                shell=True, capture_output=True, text=True
            )
            return result.stdout.strip()
        except:
            return ""
    
    def _load_memory(self) -> str:
        """Load recent memory"""
        try:
            memory_file = PRIME_HOME / "MEMORY.md"
            if memory_file.exists():
                return memory_file.read_text(encoding='utf-8')[:1000]
        except:
            pass
        return ""
    
    def _analyze_complexity(self, query: str) -> float:
        """Analyze query complexity 0-1"""
        factors = {
            "length": min(len(query) / 500, 0.2),
            "questions": query.count("?") * 0.1,
            "files": len(self._extract_files(query)) * 0.15,
            "code_keywords": sum(1 for w in ["function", "class", "implement", "code", "architecture"] if w in query.lower()) * 0.15,
            "reasoning": sum(1 for w in ["why", "how", "explain", "analyze", "compare"] if w in query.lower()) * 0.1
        }
        
        return min(sum(factors.values()), 1.0)


class APIExecutor:
    """Execute queries on cloud APIs"""
    
    def execute(self, provider: str, prompt: str, context: Context) -> str:
        """Send to specific API"""
        log(f"Sending to {provider}...")
        
        if provider == "local":
            return self._local(prompt)
        elif provider == "openai":
            return self._openai(prompt)
        elif provider == "anthropic":
            return self._anthropic(prompt)
        elif provider == "gemini":
            return self._gemini(prompt)
        elif provider == "deepseek":
            return self._deepseek(prompt)
        elif provider == "kimi":
            return self._kimi(prompt)
        
        return f"Unknown provider: {provider}"
    
    def _local(self, prompt: str) -> str:
        """Local Qwen fallback"""
        try:
            req_data = {
                "model": "qwen2.5:14b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }
            
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=json.dumps(req_data).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
                return data["message"]["content"]
        except Exception as e:
            return f"Local error: {e}"
    
    def _openai(self, prompt: str) -> str:
        """OpenAI GPT-4"""
        try:
            import httpx
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                return "Error: OPENAI_API_KEY not set"
            
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                },
                timeout=60
            )
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"OpenAI error: {e}"
    
    def _anthropic(self, prompt: str) -> str:
        """Anthropic Claude"""
        try:
            import httpx
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                return "Error: ANTHROPIC_API_KEY not set"
            
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )
            return resp.json()["content"][0]["text"]
        except Exception as e:
            return f"Anthropic error: {e}"
    
    def _gemini(self, prompt: str) -> str:
        """Google Gemini"""
        try:
            import httpx
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                return "Error: GEMINI_API_KEY not set"
            
            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=60
            )
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"Gemini error: {e}"
    
    def _deepseek(self, prompt: str) -> str:
        """DeepSeek"""
        try:
            import httpx
            key = os.environ.get("DEEPSEEK_API_KEY")
            if not key:
                return "Error: DEEPSEEK_API_KEY not set"
            
            resp = httpx.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"DeepSeek error: {e}"
    
    def _kimi(self, prompt: str) -> str:
        """Moonshot Kimi"""
        try:
            import httpx
            key = os.environ.get("KIMI_API_KEY")
            if not key:
                return "Error: KIMI_API_KEY not set"
            
            resp = httpx.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Kimi error: {e}"


class PrimeRouter:
    """Main router orchestrating all tiers"""
    
    def __init__(self):
        self.preprocessor = LocalPreprocessor()
        self.executor = APIExecutor()
    
    def process(self, query: str) -> str:
        """Process query through all 5 tiers"""
        print(f"\n{BOLD}{CYN}══════ PRIME ROUTER ══════{R}")
        print(f"Query: {query[:80]}...\n")
        
        # Tier 1-4: Local preprocessing
        draft = self.preprocessor.draft_analysis(query)
        summaries = self.preprocessor.summarize(draft)
        cleaned = self.preprocessor.clean_prompt(query, summaries)
        context = self.preprocessor.prepare_context(cleaned, draft)
        
        # Tier 5: Routing decision
        task_type, providers = self.preprocessor.route(context, cleaned)
        
        # Execute
        print(f"\n{BOLD}{CYN}══════ EXECUTION ══════{R}")
        
        if task_type == TaskType.SIMPLE:
            return self._execute_local(cleaned, context)
        
        elif task_type in [TaskType.ANALYSIS, TaskType.CODE]:
            return self._execute_single(providers[0], cleaned, context)
        
        elif task_type == TaskType.ARCHITECTURE:
            return self._execute_ensemble(providers, cleaned, context)
        
        elif task_type == TaskType.CRITICAL:
            return self._execute_critical(cleaned, context)
        
        return "Unknown task type"
    
    def _execute_local(self, query: str, ctx: Context) -> str:
        """Execute locally"""
        log("Executing locally (no API cost)")
        
        prompt = f"""Answer this query using the provided context.

Query: {query}

Files available:
{chr(10).join(ctx.files)}

Git context:
{ctx.git_context}

Provide a helpful response:"""
        
        return self.executor.execute("local", prompt, ctx)
    
    def _execute_single(self, provider: str, query: str, ctx: Context) -> str:
        """Execute on single API"""
        log(f"Executing on {provider}")
        
        prompt = f"""You are an expert assistant. Answer thoroughly.

Query: {query}

Context:
- Files: {', '.join(ctx.files)}
- Complexity: {ctx.complexity:.2f}
- Git: {ctx.git_context[:200]}

Response:"""
        
        return self.executor.execute(provider, prompt, ctx)
    
    def _execute_ensemble(self, providers: List[str], query: str, ctx: Context) -> str:
        """Execute on multiple APIs and combine"""
        log(f"Ensemble execution: {', '.join(providers)}")
        
        results = []
        for provider in providers:
            result = self._execute_single(provider, query, ctx)
            results.append(f"=== {provider.upper()} ===\n{result}\n")
        
        # Local synthesis
        synthesis_prompt = f"""Synthesize these expert opinions into one cohesive answer:

{chr(10).join(results)}

Provide a unified response that combines the best insights:"""
        
        return self.executor.execute("local", synthesis_prompt, ctx)
    
    def _execute_critical(self, query: str, ctx: Context) -> str:
        """Execute on best available API"""
        log("CRITICAL: Using best available API")
        return self._execute_single("anthropic", query, ctx)


def main():
    parser = argparse.ArgumentParser(prog="prime", description="Prime Router")
    parser.add_argument("query", help="Query to process")
    
    args = parser.parse_args()
    
    router = PrimeRouter()
    response = router.process(args.query)
    
    print(f"\n{BOLD}{CYN}══════ RESPONSE ══════{R}\n")
    print(response)
    print()


if __name__ == "__main__":
    main()
