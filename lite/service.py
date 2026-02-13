#!/usr/bin/env python3
"""
Prime Lite — Service Installer
Installs systemd/launchd service for Prime Lite
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

R = "\033[0m"
BOLD = "\033[1m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
RED = "\033[91m"

CONFIG_DIR = Path.home() / ".config" / "prime"


def install_systemd():
    """Install systemd user service (Linux)"""
    print(f"{BLU}→{R} Installing systemd service...")
    
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    
    # Find prime executable
    prime_path = subprocess.run(
        ["which", "prime"], capture_output=True, text=True
    ).stdout.strip()
    
    if not prime_path:
        # Use local path
        prime_home = os.environ.get("PRIME_HOME", str(Path.home() / ".prime"))
        prime_path = f"{prime_home}/.venv/bin/python3 {prime_home}/lite/prime-lite.py"
    else:
        prime_path = f"{prime_path} serve"
    
    service_content = f"""[Unit]
Description=Prime Lite AI Agent
Documentation=https://github.com/prime-ai/prime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={prime_path}
Restart=on-failure
RestartSec=5
Environment=PRIME_HOME={os.environ.get('PRIME_HOME', str(Path.home() / '.prime'))}
Environment=PRIME_LITE=1
Environment=PATH=/usr/local/bin:/usr/bin:/bin

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={CONFIG_DIR}

[Install]
WantedBy=default.target
"""
    
    service_file = service_dir / "prime.service"
    service_file.write_text(service_content)
    
    # Reload and enable
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "prime.service"], check=False)
    
    print(f"{GRN}✓{R} Systemd service installed")
    print(f"  Service file: {service_file}")
    print()
    print("Commands:")
    print("  systemctl --user start prime     # Start")
    print("  systemctl --user stop prime      # Stop")
    print("  systemctl --user status prime    # Status")
    print("  systemctl --user restart prime   # Restart")
    print("  journalctl --user -u prime -f    # Logs")
    print()


def install_launchd():
    """Install LaunchAgent (macOS)"""
    print(f"{BLU}→{R} Installing LaunchAgent...")
    
    launch_dir = Path.home() / "Library" / "LaunchAgents"
    launch_dir.mkdir(parents=True, exist_ok=True)
    
    # Find prime executable
    prime_path = subprocess.run(
        ["which", "prime"], capture_output=True, text=True
    ).stdout.strip()
    
    if not prime_path:
        prime_home = os.environ.get("PRIME_HOME", str(Path.home() / ".prime"))
        exe_path = f"{prime_home}/.venv/bin/python3"
        script_path = f"{prime_home}/lite/prime-lite.py"
    else:
        exe_path = "/bin/bash"
        script_path = f"-c 'exec {prime_path} serve'"
    
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ai.prime.agent</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>{exe_path}</string>
        <string>{script_path}</string>
        <string>serve</string>
    </array>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PRIME_HOME</key>
        <string>{os.environ.get('PRIME_HOME', str(Path.home() / '.prime'))}</string>
        <key>PRIME_LITE</key>
        <string>1</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>
    
    <key>StandardOutPath</key>
    <string>{CONFIG_DIR}/prime.log</string>
    
    <key>StandardErrorPath</key>
    <string>{CONFIG_DIR}/prime.error.log</string>
    
    <key>ThrottleInterval</key>
    <integer>5</integer>
</dict>
</plist>
"""
    
    plist_file = launch_dir / "ai.prime.agent.plist"
    plist_file.write_text(plist_content)
    
    # Load the agent
    subprocess.run(["launchctl", "unload", str(plist_file)], check=False, capture_output=True)
    subprocess.run(["launchctl", "load", str(plist_file)], check=False)
    
    print(f"{GRN}✓{R} LaunchAgent installed")
    print(f"  Plist file: {plist_file}")
    print()
    print("Commands:")
    print("  launchctl start ai.prime.agent     # Start")
    print("  launchctl stop ai.prime.agent      # Stop")
    print("  launchctl list | grep prime        # Status")
    print(f"  tail -f {CONFIG_DIR}/prime.log     # Logs")
    print()


def uninstall_service():
    """Remove service files"""
    print(f"{YLW}!{R} Uninstalling service...")
    
    if sys.platform == "linux":
        subprocess.run(["systemctl", "--user", "stop", "prime"], check=False, capture_output=True)
        subprocess.run(["systemctl", "--user", "disable", "prime"], check=False, capture_output=True)
        
        service_file = Path.home() / ".config" / "systemd" / "user" / "prime.service"
        if service_file.exists():
            service_file.unlink()
            print(f"{GRN}✓{R} Removed {service_file}")
        
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        
    elif sys.platform == "darwin":
        plist_file = Path.home() / "Library" / "LaunchAgents" / "ai.prime.agent.plist"
        subprocess.run(["launchctl", "unload", str(plist_file)], check=False, capture_output=True)
        
        if plist_file.exists():
            plist_file.unlink()
            print(f"{GRN}✓{R} Removed {plist_file}")
    
    print(f"{GRN}✓{R} Service uninstalled")


def start_service():
    """Start the service"""
    if sys.platform == "linux":
        subprocess.run(["systemctl", "--user", "start", "prime"])
    elif sys.platform == "darwin":
        subprocess.run(["launchctl", "start", "ai.prime.agent"])
    print(f"{GRN}✓{R} Service started")


def stop_service():
    """Stop the service"""
    if sys.platform == "linux":
        subprocess.run(["systemctl", "--user", "stop", "prime"])
    elif sys.platform == "darwin":
        subprocess.run(["launchctl", "stop", "ai.prime.agent"])
    print(f"{GRN}✓{R} Service stopped")


def status_service():
    """Check service status"""
    if sys.platform == "linux":
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "prime"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"{GRN}●{R} Service is running")
        else:
            print(f"{RED}○{R} Service is not running")
            
        # Show detailed status
        subprocess.run(["systemctl", "--user", "status", "prime", "--no-pager"])
        
    elif sys.platform == "darwin":
        result = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True
        )
        if "ai.prime.agent" in result.stdout:
            print(f"{GRN}●{R} Service is loaded")
            # Check if running
            for line in result.stdout.split("\n"):
                if "ai.prime.agent" in line:
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] != "-":
                        print(f"{GRN}●{R} Service is running (PID: {parts[0]})")
                    else:
                        print(f"{YLW}○{R} Service is loaded but not running")
        else:
            print(f"{RED}○{R} Service is not loaded")


def main():
    parser = argparse.ArgumentParser(description="Prime Lite Service Manager")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("install", help="Install service")
    subparsers.add_parser("uninstall", help="Remove service")
    subparsers.add_parser("start", help="Start service")
    subparsers.add_parser("stop", help="Stop service")
    subparsers.add_parser("restart", help="Restart service")
    subparsers.add_parser("status", help="Check service status")
    subparsers.add_parser("logs", help="View logs")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    if args.command == "install":
        if sys.platform == "linux":
            install_systemd()
        elif sys.platform == "darwin":
            install_launchd()
        else:
            print(f"{RED}✗{R} Unsupported platform: {sys.platform}")
            sys.exit(1)
            
    elif args.command == "uninstall":
        uninstall_service()
    elif args.command == "start":
        start_service()
    elif args.command == "stop":
        stop_service()
    elif args.command == "restart":
        stop_service()
        start_service()
    elif args.command == "status":
        status_service()
    elif args.command == "logs":
        if sys.platform == "linux":
            subprocess.run(["journalctl", "--user", "-u", "prime", "-f"])
        else:
            log_file = CONFIG_DIR / "prime.log"
            if log_file.exists():
                subprocess.run(["tail", "-f", str(log_file)])
            else:
                print(f"{YLW}!{R} No log file found at {log_file}")


if __name__ == "__main__":
    main()
