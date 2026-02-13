#!/usr/bin/env python3
"""
Prime Scanner Module
- Recursive project discovery (10 levels deep)
- Fuzzy file search
- File index caching
- Symlink support
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta

R = "\033[0m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"


def log(msg): print(f"  {BLU}→{R} {msg}")
def ok(msg): print(f"  {GRN}✓{R} {msg}")
def warn(msg): print(f"  {YLW}!{R} {msg}")


class ProjectScanner:
    """Recursively scan for projects"""

    # Project markers
    MARKERS = {
        ".git": "Git",
        "package.json": "Node.js",
        "pyproject.toml": "Python",
        "setup.py": "Python",
        "requirements.txt": "Python",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "pom.xml": "Java/Maven",
        "build.gradle": "Java/Gradle",
        "composer.json": "PHP",
        "Gemfile": "Ruby",
        "mix.exs": "Elixir",
        "Dockerfile": "Docker",
        "docker-compose.yml": "Docker Compose"
    }

    # Directories to skip (performance + avoiding spam)
    EXCLUDE = {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        ".cache", "dist", "build", ".next", ".nuxt", ".gradle",
        "target", "vendor", ".tox", "eggs", ".eggs", ".pytest_cache",
        ".mypy_cache", ".coverage", "htmlcov", "site-packages"
    }

    def __init__(self, max_depth: int = 10):
        self.max_depth = max_depth
        self.projects: List[Dict] = []

    def scan(self, start_path: Path) -> List[Dict]:
        """Recursively scan for projects"""
        self.projects = []
        self._walk(start_path, depth=0)
        return self.projects

    def _walk(self, path: Path, depth: int = 0):
        """Recursive directory walk"""
        if depth > self.max_depth:
            return

        if not path.exists() or not path.is_dir():
            return

        # Skip excluded directories
        if path.name in self.EXCLUDE:
            return

        try:
            # Check for project markers
            for marker, ptype in self.MARKERS.items():
                if (path / marker).exists():
                    project = {
                        "name": path.name,
                        "path": str(path),
                        "type": ptype,
                        "depth": depth
                    }

                    # Get git branch if it's a git repo
                    if marker == ".git" or (path / ".git").exists():
                        try:
                            result = subprocess.run(
                                f"cd {path} && git branch --show-current 2>/dev/null",
                                shell=True, capture_output=True, text=True, timeout=2
                            )
                            if result.stdout.strip():
                                project["git_branch"] = result.stdout.strip()
                        except:
                            pass

                    self.projects.append(project)
                    # Don't search deeper in this directory
                    return

            # Recurse into subdirectories
            try:
                for subdir in sorted(path.iterdir()):
                    if subdir.is_dir(follow_symlinks=False):
                        self._walk(subdir, depth + 1)
            except (PermissionError, OSError):
                pass

        except Exception as e:
            warn(f"Error scanning {path}: {e}")


class FileIndexer:
    """Index files for fast fuzzy search"""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "prime"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "file_index.json"
        self.index: Dict[str, str] = {}
        self._load_index()

    def _load_index(self):
        """Load cached index"""
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text())
                # Check if index is fresh (less than 1 hour old)
                timestamp = data.get("timestamp")
                if timestamp:
                    age = datetime.now() - datetime.fromisoformat(timestamp)
                    if age < timedelta(hours=1):
                        self.index = data.get("files", {})
                        return
            except:
                pass
        self.index = {}

    def _save_index(self):
        """Save index to cache"""
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "files": self.index
            }
            self.index_file.write_text(json.dumps(data))
        except:
            pass

    def build_index(self, root_path: Path, max_files: int = 10000) -> int:
        """Build file index for a directory"""
        log(f"Indexing {root_path}...")
        self.index = {}
        file_count = 0

        try:
            for path in root_path.rglob("*"):
                if file_count >= max_files:
                    warn(f"Index limit reached ({max_files} files)")
                    break

                if not path.is_file():
                    continue

                # Skip certain files
                if self._should_skip(path):
                    continue

                # Index by name (case-insensitive) and full path
                name = path.name.lower()
                self.index[name] = str(path)
                file_count += 1

        except Exception as e:
            warn(f"Indexing error: {e}")

        self._save_index()
        ok(f"Indexed {file_count} files")
        return file_count

    def _should_skip(self, path: Path) -> bool:
        """Check if file should be skipped"""
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".cache", "dist", "build", ".next", ".nuxt", ".gradle",
            "target", "vendor", ".tox", ".mypy_cache", ".pytest_cache"
        }

        skip_extensions = {
            ".o", ".a", ".so", ".dylib", ".dll", ".exe",
            ".pyc", ".pyo", ".pyd", ".swp", ".swo"
        }

        # Check if in skip directory
        if any(part in skip_dirs for part in path.parts):
            return True

        # Check extension
        if path.suffix.lower() in skip_extensions:
            return True

        # Skip large files (>100MB)
        try:
            if path.stat().st_size > 100 * 1024 * 1024:
                return True
        except:
            pass

        return False

    def find(self, pattern: str) -> List[Path]:
        """Find files matching pattern"""
        results = []

        # Direct exact match
        if pattern.lower() in self.index:
            results.append(Path(self.index[pattern.lower()]))
            return results

        # Partial match
        pattern_lower = pattern.lower()
        for name, path in self.index.items():
            if pattern_lower in name:
                results.append(Path(path))
                if len(results) >= 5:  # Limit results
                    break

        return results


class FileFinder:
    """Intelligent file finding with multiple strategies"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.indexer = FileIndexer()

    def find(self, filename: str) -> Optional[Path]:
        """
        Find file with multiple strategies:
        1. Exact match in workspace
        2. Fuzzy match in index
        3. Recursive search
        4. Standard paths
        """

        # Strategy 1: Exact path
        exact_path = self.workspace / filename
        if exact_path.exists() and exact_path.is_file():
            ok(f"Found: {exact_path}")
            return exact_path

        # Strategy 2: Index search (if available)
        indexed = self.indexer.find(filename)
        if indexed:
            ok(f"Found (indexed): {indexed[0]}")
            return indexed[0]

        # Strategy 3: Recursive glob patterns
        patterns = [
            filename,  # Exact
            f"*/{filename}",  # One level
            f"**/{filename}",  # Any depth
            f"**/src/{filename}",  # Common src dir
            f"**/app/{filename}",  # Common app dir
        ]

        for pattern in patterns:
            try:
                matches = list(self.workspace.glob(pattern))
                if matches:
                    ok(f"Found (glob): {matches[0]}")
                    return matches[0]
            except:
                pass

        # Strategy 4: Fuzzy name matching
        base_name = Path(filename).stem.lower()
        try:
            for path in self.workspace.rglob("*"):
                if path.is_file() and path.stem.lower() == base_name:
                    if path.suffix.lower() == Path(filename).suffix.lower():
                        ok(f"Found (fuzzy): {path}")
                        return path
        except:
            pass

        # Strategy 5: Standard system paths
        for std_path in [
            Path.home() / filename,
            Path("/tmp") / filename,
            Path("/etc") / filename
        ]:
            if std_path.exists():
                ok(f"Found (system): {std_path}")
                return std_path

        warn(f"File not found: {filename}")
        return None

    def find_files(self, query: str) -> List[Tuple[str, Path]]:
        """Extract and find files mentioned in query"""
        # Extract file references from query
        # Matches: "file.py", "'path/to/file.ts'", "config.json", etc.
        pattern = r'[\'"]?([\w\-./]+\.(?:py|js|ts|jsx|tsx|json|md|yaml|yml|toml|rs|go|java|cpp|c|h|sh|rb|php|java|kt|scala|clj|ex|exs|erl|rs|swift|kt|gradle|xml|pom))[\'"]?'

        matches = re.findall(pattern, query, re.IGNORECASE)
        results = []

        for match in set(matches):  # Remove duplicates
            path = self.find(match)
            if path:
                results.append((match, path))

        return results

    def read_file(self, path: str) -> Optional[str]:
        """Read file with fallback strategies"""
        found_path = self.find(path)
        if not found_path:
            return None

        try:
            return found_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            warn(f"Error reading {found_path}: {e}")
            return None

    def read_files(self, query: str) -> Dict[str, str]:
        """Read all files mentioned in query"""
        results = {}
        files = self.find_files(query)

        for name, path in files[:3]:  # Limit to 3 files
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')
                results[name] = content[:2000]  # First 2000 chars
            except:
                pass

        return results

    def list_directory(self, dirpath: str = ".") -> str:
        """List directory contents"""
        try:
            if dirpath == ".":
                target = self.workspace
            else:
                target = self.workspace / dirpath

            if not target.is_dir():
                return f"Not a directory: {target}"

            items = sorted(target.iterdir())
            lines = []

            for item in items:
                if item.is_dir():
                    lines.append(f"📁 {item.name}/")
                else:
                    size = item.stat().st_size
                    if size > 1024 * 1024:
                        size_str = f"{size / (1024*1024):.1f}MB"
                    elif size > 1024:
                        size_str = f"{size / 1024:.1f}KB"
                    else:
                        size_str = f"{size}B"
                    lines.append(f"📄 {item.name} ({size_str})")

            return "\n".join(lines) if lines else "Empty directory"

        except Exception as e:
            return f"Error: {e}"
