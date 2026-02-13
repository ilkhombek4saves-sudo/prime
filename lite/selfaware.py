#!/usr/bin/env python3
"""
Prime Self-Aware System
- Track deployment location (VPS, local, Docker, etc.)
- Monitor API key status
- Track system configuration
- Maintain deployment metadata
"""
from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

R = "\033[0m"
GRN = "\033[92m"
YLW = "\033[93m"
RED = "\033[91m"
BLU = "\033[94m"


def log(msg): print(f"  {BLU}→{R} {msg}")
def ok(msg): print(f"  {GRN}✓{R} {msg}")
def warn(msg): print(f"  {YLW}!{R} {msg}")
def error(msg): print(f"  {RED}✗{R} {msg}")


class DeploymentDetector:
    """Detect deployment environment"""

    @staticmethod
    def detect() -> Dict[str, any]:
        """Detect current deployment environment"""
        config = {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platform_release": platform.release(),
            "python_version": platform.python_version(),
            "detected_at": datetime.now().isoformat()
        }

        # Detect environment type
        if os.environ.get("DOCKER_HOST") or Path("/.dockerenv").exists():
            config["environment"] = "Docker"
            config["is_docker"] = True
        elif "google.cloud" in socket.getfqdn() or os.environ.get("GCP_PROJECT"):
            config["environment"] = "Google Cloud (GCP)"
            config["is_gcp"] = True
        elif os.environ.get("AWS_EXECUTION_ENV") or "amazonaws" in socket.getfqdn():
            config["environment"] = "AWS"
            config["is_aws"] = True
        elif os.environ.get("HEROKU_APP_NAME"):
            config["environment"] = "Heroku"
            config["is_heroku"] = True
        elif os.environ.get("VERCEL"):
            config["environment"] = "Vercel"
            config["is_vercel"] = True
        elif os.getuid() == 0:
            config["environment"] = "System (Root)"
            config["is_system"] = True
        else:
            config["environment"] = "Local/Development"
            config["is_local"] = True

        # Detect if it's a VPS by checking certain characteristics
        if socket.gethostname() != "localhost" and not "docker" in socket.gethostname().lower():
            # Check if running on a VPS by looking for signs
            try:
                # VPS-like systems often have specific patterns
                result = subprocess.run("virt-what 2>/dev/null", shell=True, capture_output=True, text=True)
                if result.stdout:
                    config["is_vps"] = True
                    config["vps_type"] = result.stdout.strip()
                    config["environment"] = f"VPS ({result.stdout.strip()})"
            except:
                pass

        return config


class ConfigManager:
    """Manage Prime configuration and state"""

    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path.home() / ".config" / "prime"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "prime.json"
        self.config = self._load_or_create()

    def _load_or_create(self) -> Dict:
        """Load existing config or create new one"""
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text())
            except:
                return self._create_default()
        return self._create_default()

    def _create_default(self) -> Dict:
        """Create default configuration"""
        detector = DeploymentDetector()
        config = {
            "version": "2.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "deployment": detector.detect(),
            "api_status": {},
            "workspace": os.getcwd(),
            "features": {
                "resilience": True,
                "caching": True,
                "fuzzy_search": True,
                "project_scanning": True
            }
        }
        self._update_config(config)
        return config

    def _update_config(self, config: Dict):
        """Save config to file"""
        config["last_updated"] = datetime.now().isoformat()
        try:
            self.config_file.write_text(json.dumps(config, indent=2))
        except:
            pass

    def get_self_info(self) -> str:
        """Get human-readable self info"""
        info_lines = [
            f"\n{BLU}{'='*60}{R}",
            f"{BLU}PRIME Self-Awareness Report{R}",
            f"{BLU}{'='*60}{R}\n",

            f"{GRN}🤖 Identity:{R}",
            f"  Name: Prime v{self.config.get('version', 'unknown')}",
            f"  Created: {self.config.get('created_at', 'unknown')[:10]}",
            f"  Last Updated: {self.config.get('last_updated', 'unknown')[:10]}\n",

            f"{GRN}📍 Location:{R}",
            f"  Hostname: {self.config['deployment'].get('hostname')}",
            f"  Environment: {self.config['deployment'].get('environment')}",
            f"  Platform: {self.config['deployment'].get('platform')} {self.config['deployment'].get('platform_release')}",
        ]

        # Add VPS info if available
        if self.config['deployment'].get('is_vps'):
            info_lines.append(f"  VPS Type: {self.config['deployment'].get('vps_type', 'Unknown')}")

        info_lines.extend([
            f"  Workspace: {self.config.get('workspace')}\n",

            f"{GRN}🔑 API Status:{R}",
        ])

        # Add API status
        api_status = self.config.get('api_status', {})
        if api_status:
            for provider, status in api_status.items():
                symbol = "✓" if status.get('available') else "✗"
                has_key = "🔑" if status.get('has_key') else "❌"
                info_lines.append(f"  {provider.upper()}: {symbol} (Key: {has_key})")
        else:
            info_lines.append("  (No API status yet - run 'prime status')\n")

        info_lines.extend([
            f"\n{GRN}⚙️  Features:{R}",
        ])

        features = self.config.get('features', {})
        for feature, enabled in features.items():
            symbol = "✓" if enabled else "✗"
            info_lines.append(f"  {feature.replace('_', ' ').title()}: {symbol}")

        info_lines.append(f"\n{BLU}{'='*60}{R}\n")

        return "\n".join(info_lines)

    def update_api_status(self, provider: str, status: Dict):
        """Update API availability status"""
        self.config["api_status"] = self.config.get("api_status", {})
        self.config["api_status"][provider] = {
            "available": status.get("available", False),
            "has_key": status.get("has_key", False),
            "checked_at": datetime.now().isoformat()
        }
        self._update_config(self.config)

    def update_workspace(self, path: Path):
        """Update workspace path"""
        self.config["workspace"] = str(path)
        self._update_config(self.config)

    def get_status_summary(self) -> Dict:
        """Get summary of Prime status"""
        return {
            "version": self.config.get('version'),
            "environment": self.config['deployment'].get('environment'),
            "hostname": self.config['deployment'].get('hostname'),
            "workspace": self.config.get('workspace'),
            "api_count": len([s for s in self.config.get('api_status', {}).values() if s.get('available')]),
            "total_apis": len(self.config.get('api_status', {}))
        }


class PrimeSelfAware:
    """Main self-aware interface"""

    def __init__(self):
        self.config_manager = ConfigManager()

    def whoami(self) -> str:
        """Who am I? Where am I?"""
        return self.config_manager.get_self_info()

    def status(self) -> Dict:
        """Get status summary"""
        return self.config_manager.get_status_summary()

    def update_api_status(self, provider: str, available: bool, has_key: bool):
        """Report API status"""
        self.config_manager.update_api_status(provider, {
            "available": available,
            "has_key": has_key
        })

    def get_config(self) -> Dict:
        """Get full configuration"""
        return self.config_manager.config

    def get_environment(self) -> str:
        """Get deployment environment"""
        return self.config_manager.config['deployment'].get('environment', 'Unknown')

    def is_vps(self) -> bool:
        """Check if running on VPS"""
        return self.config_manager.config['deployment'].get('is_vps', False)

    def is_docker(self) -> bool:
        """Check if running in Docker"""
        return self.config_manager.config['deployment'].get('is_docker', False)

    def is_local(self) -> bool:
        """Check if running locally"""
        return self.config_manager.config['deployment'].get('is_local', False)
