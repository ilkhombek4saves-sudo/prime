#!/usr/bin/env python3
"""
Prime Lite — Self Updater
Updates Prime Lite to latest version
"""
import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

R = "\033[0m"
BOLD = "\033[1m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
CYN = "\033[96m"
RED = "\033[91m"

PRIME_HOME = Path(os.environ.get("PRIME_HOME", Path.home() / ".prime"))
CONFIG_DIR = Path.home() / ".config" / "prime"
VERSION_FILE = PRIME_HOME / ".version"

# GitHub repo for releases
REPO_OWNER = "yourusername"
REPO_NAME = "prime"
GITHUB_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"


def get_current_version() -> str:
    """Get currently installed version"""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "0.0.0"


def get_latest_version() -> tuple[str, str]:
    """Get latest release version and download URL"""
    try:
        req = Request(
            f"{GITHUB_API}/releases/latest",
            headers={"Accept": "application/vnd.github.v3+json"}
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            version = data["tag_name"].lstrip("v")
            
            # Find asset for this platform
            platform = get_platform()
            download_url = None
            
            for asset in data.get("assets", []):
                if platform in asset["name"]:
                    download_url = asset["browser_download_url"]
                    break
            
            return version, download_url
    except HTTPError as e:
        if e.code == 404:
            print(f"{YLW}!{R} No releases found")
        else:
            print(f"{RED}✗{R} GitHub API error: {e}")
        return None, None
    except Exception as e:
        print(f"{RED}✗{R} Failed to check updates: {e}")
        return None, None


def get_platform() -> str:
    """Get platform identifier"""
    import platform
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if machine in ("x86_64", "amd64"):
        machine = "amd64"
    elif machine in ("arm64", "aarch64"):
        machine = "arm64"
    
    return f"{system}_{machine}"


def download_update(url: str) -> Path:
    """Download update archive"""
    print(f"{BLU}→{R} Downloading update...")
    
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        req = Request(url, headers={"User-Agent": "Prime-Updater/1.0"})
        with urlopen(req, timeout=120) as resp:
            # Show progress
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192
            
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                tmp.write(chunk)
                downloaded += len(chunk)
                
                if total:
                    progress = downloaded / total * 100
                    print(f"\r  {progress:.1f}%", end="", flush=True)
        
        print()
        return Path(tmp.name)


def backup_current() -> Path:
    """Create backup of current installation"""
    backup_dir = PRIME_HOME / ".backup"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = subprocess.run(
        ["date", "+%Y%m%d_%H%M%S"],
        capture_output=True, text=True
    ).stdout.strip()
    
    backup_path = backup_dir / f"backup_{timestamp}"
    
    print(f"{BLU}→{R} Creating backup...")
    
    # Backup main files
    files_to_backup = [
        "lite/prime-lite.py",
        "lite/secrets.py",
        "lite/service.py",
        "lite/requirements.txt",
    ]
    
    backup_path.mkdir(exist_ok=True)
    for file in files_to_backup:
        src = PRIME_HOME / file
        if src.exists():
            dst = backup_path / file
            dst.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(src, dst)
    
    # Backup version
    if VERSION_FILE.exists():
        shutil.copy2(VERSION_FILE, backup_path / ".version")
    
    print(f"{GRN}✓{R} Backup created: {backup_path}")
    return backup_path


def apply_update(archive: Path) -> bool:
    """Extract and apply update"""
    print(f"{BLU}→{R} Extracting update...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(tmpdir)
            
            # Find extracted directory
            tmp_path = Path(tmpdir)
            extracted = list(tmp_path.iterdir())
            if len(extracted) == 1 and extracted[0].is_dir():
                source = extracted[0]
            else:
                source = tmp_path
            
            # Stop service if running
            print(f"{BLU}→{R} Stopping service...")
            if sys.platform == "linux":
                subprocess.run(
                    ["systemctl", "--user", "stop", "prime"],
                    capture_output=True, check=False
                )
            elif sys.platform == "darwin":
                subprocess.run(
                    ["launchctl", "stop", "ai.prime.agent"],
                    capture_output=True, check=False
                )
            
            # Copy new files
            import shutil
            for item in source.iterdir():
                dst = PRIME_HOME / item.name
                if dst.exists():
                    if dst.is_dir():
                        shutil.rmtree(dst)
                    else:
                        dst.unlink()
                
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)
            
            print(f"{GRN}✓{R} Files updated")
            
            # Update dependencies
            print(f"{BLU}→{R} Updating dependencies...")
            venv_python = PRIME_HOME / ".venv" / "bin" / "python3"
            if venv_python.exists():
                req_file = PRIME_HOME / "lite" / "requirements.txt"
                subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-q", "-r", str(req_file)],
                    check=False, capture_output=True
                )
                print(f"{GRN}✓{R} Dependencies updated")
            
            return True
            
        except Exception as e:
            print(f"{RED}✗{R} Update failed: {e}")
            return False


def restore_backup(backup: Path):
    """Restore from backup"""
    print(f"{YLW}!{R} Restoring from backup...")
    
    import shutil
    for item in backup.iterdir():
        dst = PRIME_HOME / item.name
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        
        if item.is_dir():
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)
    
    print(f"{GRN}✓{R} Backup restored")


def start_service():
    """Start service after update"""
    print(f"{BLU}→{R} Starting service...")
    if sys.platform == "linux":
        subprocess.run(
            ["systemctl", "--user", "start", "prime"],
            capture_output=True, check=False
        )
    elif sys.platform == "darwin":
        subprocess.run(
            ["launchctl", "start", "ai.prime.agent"],
            capture_output=True, check=False
        )


def check_update():
    """Check for available updates"""
    print(f"{BOLD}{CYN}Prime Lite Updater{R}")
    print()
    
    current = get_current_version()
    print(f"Current version: {current}")
    
    latest, url = get_latest_version()
    if not latest:
        print(f"{YLW}!{R} Could not determine latest version")
        return
    
    print(f"Latest version:  {latest}")
    print()
    
    if latest == current:
        print(f"{GRN}✓{R} Already up to date!")
        return
    
    # Compare versions
    def parse_version(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))
    
    if parse_version(latest) > parse_version(current):
        print(f"{YLW}!{R} Update available!")
        print(f"  Run: prime update --apply")
    else:
        print(f"{GRN}✓{R} Current version is newer than release")


def apply_update_flow(force: bool = False):
    """Apply update flow"""
    print(f"{BOLD}{CYN}Prime Lite Updater{R}")
    print()
    
    current = get_current_version()
    print(f"Current version: {current}")
    
    latest, url = get_latest_version()
    if not latest:
        print(f"{RED}✗{R} Could not determine latest version")
        return False
    
    print(f"Latest version:  {latest}")
    
    if latest == current and not force:
        print(f"{GRN}✓{R} Already up to date!")
        return True
    
    if not url:
        print(f"{RED}✗{R} No download available for your platform: {get_platform()}")
        return False
    
    print()
    if not force:
        response = input(f"Update to v{latest}? [Y/n]: ").strip().lower()
        if response and response not in ("y", "yes"):
            print("Cancelled")
            return False
    
    # Backup
    backup = backup_current()
    
    # Download
    try:
        archive = download_update(url)
    except Exception as e:
        print(f"{RED}✗{R} Download failed: {e}")
        return False
    
    # Apply
    if apply_update(archive):
        # Update version file
        VERSION_FILE.write_text(latest)
        
        # Cleanup
        archive.unlink()
        
        print()
        print(f"{GRN}✓{R} Updated to v{latest}!")
        
        # Start service
        start_service()
        
        print()
        print("Run 'prime status' to verify")
        return True
    else:
        # Restore backup
        restore_backup(backup)
        start_service()
        return False


def main():
    parser = argparse.ArgumentParser(
        prog="prime-update",
        description="Prime Lite Self Updater"
    )
    parser.add_argument(
        "--apply", "-a",
        action="store_true",
        help="Apply available update"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force reinstall current version"
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Check for updates only"
    )
    
    args = parser.parse_args()
    
    if args.check:
        check_update()
    elif args.apply or args.force:
        apply_update_flow(force=args.force)
    else:
        check_update()


if __name__ == "__main__":
    main()
