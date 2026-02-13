#!/usr/bin/env python3
"""
Prime Lite — Secure Secrets Management
Uses system keyring for secure credential storage
"""
import getpass
import json
import os
from pathlib import Path
from typing import Optional

# Try to import keyring
try:
    import keyring
    from keyring.errors import PasswordDeleteError
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

CONFIG_DIR = Path.home() / ".config" / "prime"
SECRETS_FILE = CONFIG_DIR / ".secrets"

APP_NAME = "prime-lite"


class SecureStorage:
    """Secure storage for secrets using system keyring or encrypted file"""
    
    def __init__(self):
        self._fallback_mode = not KEYRING_AVAILABLE
        self._cache = {}
        
        if self._fallback_mode:
            print("⚠️  Keyring not available, using encrypted file storage")
    
    def _get_fallback_path(self, service: str) -> Path:
        """Get path for fallback encrypted storage"""
        return CONFIG_DIR / f".secret_{service}"
    
    def _encrypt(self, data: str) -> bytes:
        """Simple XOR encryption with machine-specific key"""
        # Use machine-id or hostname as key
        key = self._get_machine_key()
        return bytes([ord(c) ^ key[i % len(key)] for i, c in enumerate(data)])
    
    def _decrypt(self, data: bytes) -> str:
        """Decrypt XOR encrypted data"""
        key = self._get_machine_key()
        return "".join([chr(b ^ key[i % len(key)]) for i, b in enumerate(data)])
    
    def _get_machine_key(self) -> bytes:
        """Get machine-specific key for encryption"""
        # Try to get machine ID
        key_sources = [
            "/etc/machine-id",
            "/var/lib/dbus/machine-id",
        ]
        
        for source in key_sources:
            if os.path.exists(source):
                return Path(source).read_text().strip().encode()
        
        # Fallback to hostname
        return os.uname().nodename.encode()
    
    def set(self, service: str, username: str, password: str) -> bool:
        """Store a secret"""
        try:
            if not self._fallback_mode:
                keyring.set_password(f"{APP_NAME}/{service}", username, password)
            else:
                # Fallback: encrypted file
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                data = json.dumps({"username": username, "password": password})
                encrypted = self._encrypt(data)
                self._get_fallback_path(service).write_bytes(encrypted)
            
            self._cache[service] = (username, password)
            return True
        except Exception as e:
            print(f"Error storing secret: {e}")
            return False
    
    def get(self, service: str, username: Optional[str] = None) -> Optional[str]:
        """Retrieve a secret"""
        # Check cache first
        if service in self._cache:
            return self._cache[service][1]
        
        try:
            if not self._fallback_mode:
                # If username not provided, try common ones
                if username is None:
                    for u in ["api_key", "token", "default", "prime"]:
                        result = keyring.get_password(f"{APP_NAME}/{service}", u)
                        if result:
                            self._cache[service] = (u, result)
                            return result
                    return None
                else:
                    result = keyring.get_password(f"{APP_NAME}/{service}", username)
                    if result:
                        self._cache[service] = (username, result)
                    return result
            else:
                # Fallback: encrypted file
                path = self._get_fallback_path(service)
                if path.exists():
                    encrypted = path.read_bytes()
                    data = json.loads(self._decrypt(encrypted))
                    password = data.get("password")
                    if password:
                        self._cache[service] = (data.get("username", ""), password)
                    return password
                return None
        except Exception as e:
            print(f"Error retrieving secret: {e}")
            return None
    
    def delete(self, service: str, username: Optional[str] = None) -> bool:
        """Delete a secret"""
        try:
            if not self._fallback_mode:
                if username:
                    keyring.delete_password(f"{APP_NAME}/{service}", username)
                else:
                    # Try to delete all common usernames
                    for u in ["api_key", "token", "default", "prime"]:
                        try:
                            keyring.delete_password(f"{APP_NAME}/{service}", u)
                        except PasswordDeleteError:
                            pass
            else:
                path = self._get_fallback_path(service)
                if path.exists():
                    path.unlink()
            
            self._cache.pop(service, None)
            return True
        except Exception as e:
            print(f"Error deleting secret: {e}")
            return False
    
    def list_services(self) -> list[str]:
        """List all stored services"""
        try:
            if not self._fallback_mode and hasattr(keyring, 'get_keyring'):
                kr = keyring.get_keyring()
                if hasattr(kr, 'get_preferred_collection'):
                    # SecretService backend
                    return []
            
            # Fallback: list files
            if CONFIG_DIR.exists():
                services = []
                for f in CONFIG_DIR.glob(".secret_*"):
                    service = f.name[8:]  # Remove .secret_ prefix
                    services.append(service)
                return services
            return []
        except Exception:
            return []
    
    def migrate_from_env(self) -> dict[str, bool]:
        """Migrate secrets from .env to secure storage"""
        env_file = CONFIG_DIR / ".env"
        results = {}
        
        if not env_file.exists():
            return results
        
        secrets_to_migrate = [
            ("TELEGRAM_BOT_TOKEN", "telegram"),
            ("OPENAI_API_KEY", "openai"),
            ("ANTHROPIC_AUTH_TOKEN", "anthropic"),
            ("DEEPSEEK_API_KEY", "deepseek"),
            ("KIMI_API_KEY", "kimi"),
            ("GEMINI_API_KEY", "gemini"),
            ("ZAI_API_KEY", "zai"),
        ]
        
        env_content = env_file.read_text()
        new_lines = []
        
        for env_var, service_name in secrets_to_migrate:
            for line in env_content.split("\n"):
                if line.startswith(f"{env_var}=") and len(line) > len(env_var) + 1:
                    value = line[len(env_var)+1:].strip()
                    if value:
                        success = self.set(service_name, "api_key", value)
                        results[env_var] = success
                        if success:
                            # Comment out in .env
                            new_lines.append(f"# {line}  # Migrated to keyring")
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                    break
            else:
                new_lines.append(line)
        
        # Write updated .env
        env_file.write_text("\n".join(new_lines))
        
        return results


# CLI interface
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Prime Lite Secure Storage")
    subparsers = parser.add_subparsers(dest="command")
    
    # Set secret
    set_parser = subparsers.add_parser("set", help="Store a secret")
    set_parser.add_argument("service", help="Service name (e.g., telegram, openai)")
    set_parser.add_argument("--value", help="Secret value (or will prompt)")
    
    # Get secret
    get_parser = subparsers.add_parser("get", help="Retrieve a secret")
    get_parser.add_argument("service", help="Service name")
    
    # Delete secret
    del_parser = subparsers.add_parser("delete", help="Delete a secret")
    del_parser.add_argument("service", help="Service name")
    
    # List secrets
    subparsers.add_parser("list", help="List stored services")
    
    # Migrate from .env
    subparsers.add_parser("migrate", help="Migrate secrets from .env to keyring")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    storage = SecureStorage()
    
    if args.command == "set":
        value = args.value
        if not value:
            value = getpass.getpass(f"Enter secret for {args.service}: ")
        
        if storage.set(args.service, "api_key", value):
            print(f"✓ Stored secret for {args.service}")
        else:
            print(f"✗ Failed to store secret")
    
    elif args.command == "get":
        value = storage.get(args.service)
        if value:
            # Mask most of it
            masked = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "****"
            print(f"Secret for {args.service}: {masked}")
        else:
            print(f"No secret found for {args.service}")
    
    elif args.command == "delete":
        if storage.delete(args.service):
            print(f"✓ Deleted secret for {args.service}")
        else:
            print(f"✗ Failed to delete secret")
    
    elif args.command == "list":
        services = storage.list_services()
        if services:
            print("Stored services:")
            for s in services:
                print(f"  - {s}")
        else:
            print("No stored secrets found")
    
    elif args.command == "migrate":
        print("Migrating secrets from .env to secure storage...")
        results = storage.migrate_from_env()
        if results:
            for var, success in results.items():
                status = "✓" if success else "✗"
                print(f"  {status} {var}")
        else:
            print("No secrets found to migrate")


if __name__ == "__main__":
    main()
