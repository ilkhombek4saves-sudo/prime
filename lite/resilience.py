#!/usr/bin/env python3
"""
Prime Resilience Module
- API retry with exponential backoff
- Fallback to local Ollama
- Internet connectivity checks
- Result caching
- Provider availability verification
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple

R = "\033[0m"
GRN = "\033[92m"
YLW = "\033[93m"
RED = "\033[91m"
BLU = "\033[94m"


def log(msg): print(f"  {BLU}→{R} {msg}")
def ok(msg): print(f"  {GRN}✓{R} {msg}")
def warn(msg): print(f"  {YLW}!{R} {msg}")
def error(msg): print(f"  {RED}✗{R} {msg}")


class ResultCache:
    """Simple file-based cache for API results"""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "prime"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "api_cache.json"
        self._cache = self._load_cache()

    def _load_cache(self) -> Dict:
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text())
            except:
                return {}
        return {}

    def _save_cache(self):
        try:
            self.cache_file.write_text(json.dumps(self._cache, indent=2))
        except:
            pass

    def get(self, key: str, ttl_minutes: int = 60) -> Optional[str]:
        """Get cached result if not expired"""
        if key not in self._cache:
            return None

        entry = self._cache[key]
        expires = datetime.fromisoformat(entry["expires"])

        if datetime.now() < expires:
            log(f"Cache hit for: {key[:50]}...")
            return entry["result"]

        # Expired
        del self._cache[key]
        self._save_cache()
        return None

    def set(self, key: str, result: str, ttl_minutes: int = 60):
        """Cache result with TTL"""
        self._cache[key] = {
            "result": result,
            "expires": (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat()
        }
        self._save_cache()

    def clear_expired(self):
        """Remove expired entries"""
        now = datetime.now()
        expired_keys = [
            k for k, v in self._cache.items()
            if datetime.fromisoformat(v["expires"]) < now
        ]
        for k in expired_keys:
            del self._cache[k]
        if expired_keys:
            self._save_cache()


class ConnectivityChecker:
    """Check internet connectivity"""

    @staticmethod
    def has_internet(timeout: int = 3) -> bool:
        """Check if internet is available"""
        try:
            # Try multiple methods for robustness
            socket.create_connection(("8.8.8.8", 53), timeout=timeout)
            return True
        except (OSError, socket.timeout):
            pass

        try:
            urllib.request.urlopen("http://www.google.com", timeout=timeout)
            return True
        except:
            pass

        return False

    @staticmethod
    def check_api_availability(api_url: str, timeout: int = 2) -> bool:
        """Check if specific API is reachable"""
        try:
            req = urllib.request.Request(api_url, method="HEAD")
            with urllib.request.urlopen(req, timeout=timeout):
                return True
        except:
            return False


class APIExecutor:
    """Execute API calls with resilience"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.cache = ResultCache()
        self.connectivity = ConnectivityChecker()

    def execute_with_fallback(
        self,
        provider: str,
        prompt: str,
        context: str = ""
    ) -> str:
        """
        Execute API call with retry, fallback, and caching
        Returns: (success: bool, result: str)
        """

        # Generate cache key
        cache_key = self._make_cache_key(provider, prompt)

        # Check cache first
        cached = self.cache.get(cache_key)
        if cached:
            return True, cached

        # Check internet
        if not self.connectivity.has_internet():
            warn("No internet connection - using local Ollama")
            return self._execute_local(prompt, context, fallback=True)

        # Try API with retries
        for attempt in range(self.max_retries):
            try:
                log(f"API [{provider}] attempt {attempt + 1}/{self.max_retries}")

                # Execute based on provider
                if provider == "openai":
                    result = self._execute_openai(prompt)
                elif provider == "anthropic":
                    result = self._execute_anthropic(prompt)
                elif provider == "gemini":
                    result = self._execute_gemini(prompt)
                elif provider == "deepseek":
                    result = self._execute_deepseek(prompt)
                elif provider == "kimi":
                    result = self._execute_kimi(prompt)
                elif provider == "local":
                    return self._execute_local(prompt, context)
                else:
                    return False, f"Unknown provider: {provider}"

                # Success - cache and return
                self.cache.set(cache_key, result)
                ok(f"API {provider} success")
                return True, result

            except (ConnectionError, TimeoutError, urllib.error.URLError) as e:
                delay = self.base_delay * (2 ** attempt)
                if attempt < self.max_retries - 1:
                    warn(f"Attempt {attempt + 1} failed: {str(e)[:50]}. Retry in {delay}s...")
                    time.sleep(delay)
                else:
                    error(f"API {provider} failed after {self.max_retries} attempts")

            except Exception as e:
                error(f"API {provider} error: {str(e)[:100]}")
                break

        # Fallback to local
        warn(f"Falling back to local Ollama")
        return self._execute_local(prompt, context, fallback=True)

    def _execute_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        try:
            import httpx
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                raise ValueError("OPENAI_API_KEY not set")

            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                },
                timeout=60.0
            )

            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise ConnectionError(f"OpenAI: {e}")

    def _execute_anthropic(self, prompt: str) -> str:
        """Call Anthropic API"""
        try:
            import httpx
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError("ANTHROPIC_API_KEY not set")

            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60.0
            )

            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

            return resp.json()["content"][0]["text"]
        except Exception as e:
            raise ConnectionError(f"Anthropic: {e}")

    def _execute_gemini(self, prompt: str) -> str:
        """Call Gemini API"""
        try:
            import httpx
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise ValueError("GEMINI_API_KEY not set")

            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=60.0
            )

            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            raise ConnectionError(f"Gemini: {e}")

    def _execute_deepseek(self, prompt: str) -> str:
        """Call DeepSeek API"""
        try:
            import httpx
            key = os.environ.get("DEEPSEEK_API_KEY")
            if not key:
                raise ValueError("DEEPSEEK_API_KEY not set")

            resp = httpx.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60.0
            )

            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise ConnectionError(f"DeepSeek: {e}")

    def _execute_kimi(self, prompt: str) -> str:
        """Call Kimi API"""
        try:
            import httpx
            key = os.environ.get("KIMI_API_KEY")
            if not key:
                raise ValueError("KIMI_API_KEY not set")

            resp = httpx.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60.0
            )

            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise ConnectionError(f"Kimi: {e}")

    def _execute_local(self, prompt: str, context: str = "", fallback: bool = False) -> Tuple[bool, str]:
        """Execute on local Ollama"""
        try:
            log("Local Ollama processing...")

            req_data = {
                "model": "qwen2.5:7b",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant. Be concise."},
                    {"role": "user", "content": prompt}
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
                result = data["message"]["content"]
                ok("Local Ollama success")
                return True, result

        except Exception as e:
            error(f"Local Ollama error: {e}")
            return False, f"Error: Could not reach Ollama at localhost:11434"

    def check_provider_availability(self, provider: str) -> Dict[str, any]:
        """Check if provider is available"""
        status = {
            "provider": provider,
            "available": False,
            "has_key": False,
            "internet_ok": self.connectivity.has_internet()
        }

        if provider == "local":
            try:
                urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
                status["available"] = True
                ok(f"Local Ollama: OK")
            except:
                warn(f"Local Ollama: OFFLINE")
            return status

        # Check API key
        key_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "kimi": "KIMI_API_KEY"
        }

        key_var = key_vars.get(provider)
        if key_var:
            status["has_key"] = bool(os.environ.get(key_var))

        if not status["has_key"]:
            warn(f"{provider}: No API key set")
            return status

        if not status["internet_ok"]:
            warn(f"{provider}: No internet")
            return status

        # Try to connect
        endpoints = {
            "openai": "https://api.openai.com/v1/models",
            "anthropic": "https://api.anthropic.com/v1/messages",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
            "deepseek": "https://api.deepseek.com/chat/completions",
            "kimi": "https://api.moonshot.cn/v1/chat/completions"
        }

        endpoint = endpoints.get(provider)
        if endpoint:
            status["available"] = self.connectivity.check_api_availability(endpoint)
            if status["available"]:
                ok(f"{provider}: Available")
            else:
                warn(f"{provider}: Unreachable")

        return status

    def _make_cache_key(self, provider: str, prompt: str) -> str:
        """Generate cache key from provider and prompt"""
        import hashlib
        key_str = f"{provider}:{prompt[:200]}"
        return hashlib.md5(key_str.encode()).hexdigest()
