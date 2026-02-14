#!/usr/bin/env python3
"""
Prime CLI - Command line interface for Prime AI Platform
Inspired by OpenClaw's UX
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests

# Colors
RED = '\033[91m'
GRN = '\033[92m'
YLW = '\033[93m'
BLU = '\033[94m'
RST = '\033[0m'
BOLD = '\033[1m'

PRIME_DIR = Path(os.environ.get('PRIME_HOME', Path.home() / 'prime'))
API_BASE = 'http://localhost:8000/api'


def log(msg: str): print(f"{BLU}→{RST} {msg}")
def ok(msg: str): print(f"{GRN}✓{RST} {msg}")
def warn(msg: str): print(f"{YLW}!{RST} {msg}")
def error(msg: str): print(f"{RED}✗{RST} {msg}", file=sys.stderr)
def step(msg: str): 
    print()
    print(f"{BLU}{'═' * 51}{RST}")
    print(f"{BOLD}  {msg}{RST}")
    print(f"{BLU}{'═' * 51}{RST}")


def check_docker() -> bool:
    """Check if Docker is running"""
    try:
        subprocess.run(['docker', 'info'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def api_get(endpoint: str, timeout: int = 5) -> Optional[dict]:
    """Make GET request to API"""
    try:
        resp = requests.get(f"{API_BASE}/{endpoint}", timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def api_post(endpoint: str, data: dict, timeout: int = 10) -> Optional[dict]:
    """Make POST request to API"""
    try:
        resp = requests.post(
            f"{API_BASE}/{endpoint}",
            json=data,
            timeout=timeout
        )
        if resp.status_code in (200, 201):
            return resp.json()
        return {"error": resp.text, "status": resp.status_code}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# SETUP WIZARD
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_setup(args):
    """Interactive setup wizard"""
    step("Prime Setup Wizard")
    
    # 1. Check Docker
    log("Проверка Docker...")
    if not check_docker():
        error("Docker не запущен. Запусти: sudo systemctl start docker")
        return 1
    ok("Docker работает")
    
    # 2. Check if already running
    log("Проверка статуса Prime...")
    health = api_get('healthz')
    if health:
        ok("Prime уже запущен")
    else:
        log("Запуск Prime...")
        os.chdir(PRIME_DIR)
        subprocess.run(['docker', 'compose', 'up', '-d'], check=True)
        
        # Wait for startup
        for i in range(30):
            if api_get('healthz'):
                ok("Prime запущен")
                break
            time.sleep(1)
            print(".", end='', flush=True)
        else:
            error("Prime не запустился")
            return 1
    
    # 3. Check onboard status
    step("Настройка администратора")
    onboard = api_get('onboard/status')
    
    if onboard and onboard.get('onboard_required'):
        log("Создание первого администратора...")
        
        username = input("Username [admin]: ").strip() or "admin"
        import secrets
        auto_pass = secrets.token_urlsafe(12)[:16]
        password = input(f"Password [авто: {auto_pass}]: ").strip() or auto_pass
        
        result = api_post('onboard', {'username': username, 'password': password})
        if result and 'username' in result:
            ok(f"Администратор {username} создан")
            
            # Save credentials
            creds_file = PRIME_DIR / '.admin_credentials'
            creds_file.write_text(f"# Prime Admin Credentials\nUsername: {username}\nPassword: {password}\n")
            creds_file.chmod(0o600)
            
            print(f"\n{YLW}{'═' * 51}{RST}")
            print(f"{BOLD}  ADMIN CREDENTIALS{RST}")
            print(f"{YLW}{'═' * 51}{RST}")
            print(f"  Username: {BOLD}{username}{RST}")
            print(f"  Password: {BOLD}{password}{RST}")
            print(f"\n{RED}⚠ Смени пароль после первого входа!{RST}")
        else:
            error("Не удалось создать администратора")
    else:
        ok("Администратор уже настроен")
    
    # 4. Setup AI Providers
    step("Настройка AI провайдеров")
    providers = [
        ('OpenAI', 'OPENAI_API_KEY', 'sk-...'),
        ('Google Gemini', 'GEMINI_API_KEY', 'AI...'),
        ('Mistral', 'MISTRAL_API_KEY', '...'),
        ('DeepSeek', 'DEEPSEEK_API_KEY', '...'),
        ('Qwen', 'QWEN_API_KEY', '...'),
        ('Kimi', 'KIMI_API_KEY', '...'),
        ('ZAI', 'ZAI_API_KEY', '...'),
    ]
    
    env_file = PRIME_DIR / '.env'
    env_content = env_file.read_text() if env_file.exists() else ""
    
    added = []
    for name, var, hint in providers:
        key = input(f"{name} [{hint}]: ").strip()
        if key:
            # Update .env
            if f"{var}=" in env_content:
                # Replace existing
                import re
                env_content = re.sub(
                    rf"#?\s*{var}=.*\n",
                    f"{var}={key}\n",
                    env_content
                )
            else:
                env_content += f"\n{var}={key}"
            added.append(name)
    
    if added:
        env_file.write_text(env_content)
        ok(f"Добавлены провайдеры: {', '.join(added)}")
        log("Перезапуск для применения изменений...")
        os.chdir(PRIME_DIR)
        subprocess.run(['docker', 'compose', 'restart', 'backend'], check=True)
    else:
        warn("Нет провайдеров. Добавь позже в .env")
    
    # 5. Setup Channels
    step("Настройка каналов связи")
    telegram = input("Telegram Bot Token (или Enter пропустить): ").strip()
    discord = input("Discord Bot Token (или Enter пропустить): ").strip()
    
    if telegram or discord:
        # Add to .env
        env_content = env_file.read_text() if env_file.exists() else ""
        if telegram:
            if "TELEGRAM_BOT_TOKEN=" in env_content:
                import re
                env_content = re.sub(
                    r"#?\s*TELEGRAM_BOT_TOKEN=.*\n",
                    f"TELEGRAM_BOT_TOKEN={telegram}\n",
                    env_content
                )
            else:
                env_content += f"\nTELEGRAM_BOT_TOKEN={telegram}"
            ok("Telegram настроен")
        
        if discord:
            if "DISCORD_BOT_TOKEN=" in env_content:
                import re
                env_content = re.sub(
                    r"#?\s*DISCORD_BOT_TOKEN=.*\n",
                    f"DISCORD_BOT_TOKEN={discord}\n",
                    env_content
                )
            else:
                env_content += f"\nDISCORD_BOT_TOKEN={discord}"
            ok("Discord настроен")
        
        env_file.write_text(env_content)
        log("Перезапуск...")
        os.chdir(PRIME_DIR)
        subprocess.run(['docker', 'compose', 'restart'], check=True)
    
    # 6. Create first agent
    step("Создание первого агента")
    create = input("Создать агента сейчас? [Y/n]: ").strip().lower() != 'n'
    
    if create:
        name = input("Имя агента [assistant]: ").strip() or "assistant"
        
        # Create agent via API
        result = api_post('agents', {
            'name': name,
            'system_prompt': 'You are a helpful AI assistant.',
            'memory_enabled': True,
            'web_search_enabled': False,
        })
        
        if result and 'id' in result:
            ok(f"Агент '{name}' создан")
            
            # Setup binding for Telegram if configured
            if telegram:
                log("Настройка Telegram binding...")
                # Get bot ID from Telegram
                import re
                bot_id_match = re.match(r'(\d+):', telegram)
                if bot_id_match:
                    bot_id = bot_id_match.group(1)
                    # Create bot record
                    bot_result = api_post('bots', {
                        'name': f'telegram_{bot_id}',
                        'token': telegram,
                        'platform': 'telegram',
                        'active': True,
                    })
                    if bot_result and 'id' in bot_result:
                        # Create binding
                        bind_result = api_post('bindings', {
                            'bot_id': bot_result['id'],
                            'agent_id': result['id'],
                            'channel': 'telegram',
                            'dm_policy': 'open',
                        })
                        if bind_result:
                            ok("Telegram привязан к агенту")
        else:
            warn("Не удалось создать агента. Создай вручную через API.")
    
    # 7. Summary
    step("Setup Complete")
    print(f"{GRN}Prime готов к работе!{RST}")
    print(f"\nAPI: {BLU}http://localhost:8000{RST}")
    print(f"Docs: {BLU}http://localhost:8000/docs{RST}")
    print(f"\nКоманды:")
    print(f"  prime doctor      # Проверка здоровья")
    print(f"  prime status      # Статус")
    print(f"  prime logs        # Логи")
    print(f"  prime agents list # Список агентов")
    
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_doctor(args):
    """Run diagnostics"""
    step("Prime Doctor")
    
    checks = []
    
    # 1. Docker
    log("Проверка Docker...")
    if check_docker():
        ok("Docker запущен")
        checks.append(("Docker", True, "OK"))
    else:
        error("Docker не запущен")
        checks.append(("Docker", False, "Not running"))
    
    # 2. API
    log("Проверка API...")
    health = api_get('healthz')
    if health:
        ok("API отвечает")
        checks.append(("API", True, "OK"))
    else:
        error("API не отвечает")
        checks.append(("API", False, "Not responding"))
        
        # Try to start
        if args.fix:
            log("Попытка запуска...")
            os.chdir(PRIME_DIR)
            subprocess.run(['docker', 'compose', 'up', '-d'], capture_output=True)
            time.sleep(3)
            health = api_get('healthz')
            if health:
                ok("Prime запущен")
                checks[-1] = ("API", True, "Started")
    
    # 3. Database
    if health:
        log("Проверка базы данных...")
        doctor = api_get('doctor')
        if doctor:
            db_status = doctor.get('database', {}).get('status', 'unknown')
            if db_status == 'connected':
                ok("База данных подключена")
                checks.append(("Database", True, "Connected"))
            else:
                warn(f"База данных: {db_status}")
                checks.append(("Database", False, db_status))
            
            # 4. Providers
            log("Проверка провайдеров...")
            providers = doctor.get('providers', [])
            for p in providers:
                name = p.get('name', 'unknown')
                status = p.get('status', 'unknown')
                if status == 'active':
                    ok(f"Провайдер {name}: активен")
                    checks.append((f"Provider {name}", True, "Active"))
                else:
                    error = p.get('error', 'unknown error')
                    warn(f"Провайдер {name}: {error}")
                    checks.append((f"Provider {name}", False, error))
        else:
            warn("Не удалось получить статус от API")
    
    # Summary
    print()
    print(f"{BLU}{'═' * 51}{RST}")
    print(f"{BOLD}  РЕЗУЛЬТАТЫ ПРОВЕРКИ{RST}")
    print(f"{BLU}{'═' * 51}{RST}")
    
    passed = sum(1 for _, ok_status, _ in checks if ok_status)
    total = len(checks)
    
    for name, ok_status, msg in checks:
        icon = f"{GRN}✓{RST}" if ok_status else f"{RED}✗{RST}"
        print(f"  {icon} {name}: {msg}")
    
    print()
    if passed == total:
        print(f"{GRN}Все проверки пройдены!{RST}")
        return 0
    else:
        print(f"{YLW}Пройдено {passed}/{total} проверок{RST}")
        return 1


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_status(args):
    """Show status"""
    health = api_get('healthz')
    if not health:
        error("Prime не запущен")
        return 1
    
    print(f"{BLU}{'═' * 51}{RST}")
    print(f"{BOLD}  PRIME STATUS{RST}")
    print(f"{BLU}{'═' * 51}{RST}")
    
    print(f"\n{BOLD}Gateway:{RST} {GRN}Running{RST}")
    print(f"{BOLD}Version:{RST} {health.get('version', 'unknown')}")
    print(f"{BOLD}Uptime:{RST} {health.get('uptime', 'unknown')}")
    
    # Get more details
    doctor = api_get('doctor')
    if doctor:
        print(f"\n{BOLD}Database:{RST} {doctor.get('database', {}).get('status', 'unknown')}")
        
        providers = doctor.get('providers', [])
        if providers:
            print(f"\n{BOLD}Providers:{RST}")
            for p in providers:
                name = p.get('name', 'unknown')
                status = p.get('status', 'unknown')
                icon = f"{GRN}●{RST}" if status == 'active' else f"{RED}●{RST}"
                print(f"  {icon} {name}: {status}")
    
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# LOGS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_logs(args):
    """Show logs"""
    service = args.service if hasattr(args, 'service') and args.service else None
    
    os.chdir(PRIME_DIR)
    cmd = ['docker', 'compose', 'logs', '-f']
    if service:
        cmd.append(service)
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_agents(args):
    """Manage agents"""
    if args.agents_command == 'list':
        agents = api_get('agents')
        if not agents:
            print("Нет агентов")
            return 0
        
        print(f"{BLU}{'═' * 51}{RST}")
        print(f"{BOLD}  AGENTS{RST}")
        print(f"{BLU}{'═' * 51}{RST}")
        
        for a in agents:
            active = f"{GRN}●{RST}" if a.get('active') else f"{RED}●{RST}"
            print(f"\n  {active} {BOLD}{a.get('name', 'unnamed')}{RST}")
            print(f"     ID: {a.get('id', 'unknown')}")
            print(f"     Memory: {'on' if a.get('memory_enabled') else 'off'}")
            print(f"     Web search: {'on' if a.get('web_search_enabled') else 'off'}")
    
    elif args.agents_command == 'create':
        name = input("Name: ").strip()
        if not name:
            error("Имя обязательно")
            return 1
        
        system = input("System prompt (или Enter для дефолта): ").strip()
        
        result = api_post('agents', {
            'name': name,
            'system_prompt': system or 'You are a helpful AI assistant.',
            'memory_enabled': True,
        })
        
        if result and 'id' in result:
            ok(f"Агент '{name}' создан")
        else:
            error("Не удалось создать агента")
            return 1
    
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# CHANNELS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_channels(args):
    """Manage channels"""
    if args.channels_command == 'list':
        bots = api_get('bots')
        if not bots:
            print("Нет подключенных каналов")
            return 0
        
        print(f"{BLU}{'═' * 51}{RST}")
        print(f"{BOLD}  CHANNELS{RST}")
        print(f"{BLU}{'═' * 51}{RST}")
        
        for b in bots:
            active = f"{GRN}●{RST}" if b.get('active') else f"{RED}●{RST}"
            print(f"  {active} {b.get('platform', 'unknown')}: {b.get('name', 'unnamed')}")
    
    elif args.channels_command == 'add':
        platform = input("Platform (telegram/discord): ").strip().lower()
        token = input("Bot Token: ").strip()
        name = input("Name: ").strip() or f"{platform}_bot"
        
        if not token:
            error("Token обязателен")
            return 1
        
        result = api_post('bots', {
            'name': name,
            'token': token,
            'platform': platform,
            'active': True,
        })
        
        if result and 'id' in result:
            ok(f"Канал '{name}' добавлен")
            
            # Ask for binding
            create_binding = input("Привязать к агенту сейчас? [Y/n]: ").strip().lower() != 'n'
            if create_binding:
                agents = api_get('agents')
                if agents:
                    print("\nДоступные агенты:")
                    for i, a in enumerate(agents, 1):
                        print(f"  {i}. {a.get('name')}")
                    
                    choice = input("Выбери номер агента: ").strip()
                    try:
                        agent = agents[int(choice) - 1]
                        bind_result = api_post('bindings', {
                            'bot_id': result['id'],
                            'agent_id': agent['id'],
                            'channel': platform,
                            'dm_policy': 'open',
                        })
                        if bind_result:
                            ok(f"Привязан к агенту '{agent['name']}'")
                    except (ValueError, IndexError):
                        warn("Неверный выбор")
        else:
            error("Не удалось добавить канал")
            return 1
    
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Prime CLI - AI Agent Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  prime setup              # Run setup wizard
  prime doctor             # Check health
  prime doctor --fix       # Auto-fix issues
  prime status             # Show status
  prime logs               # Show logs
  prime logs backend       # Show backend logs
  prime agents list        # List agents
  prime agents create      # Create new agent
  prime channels list      # List channels
  prime channels add       # Add new channel
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # setup
    setup_parser = subparsers.add_parser('setup', help='Run setup wizard')
    
    # doctor
    doctor_parser = subparsers.add_parser('doctor', help='Run diagnostics')
    doctor_parser.add_argument('--fix', action='store_true', help='Auto-fix issues')
    
    # status
    status_parser = subparsers.add_parser('status', help='Show status')
    
    # logs
    logs_parser = subparsers.add_parser('logs', help='Show logs')
    logs_parser.add_argument('service', nargs='?', help='Service name (backend, db, etc.)')
    
    # agents
    agents_parser = subparsers.add_parser('agents', help='Manage agents')
    agents_sub = agents_parser.add_subparsers(dest='agents_command')
    agents_sub.add_parser('list', help='List agents')
    agents_sub.add_parser('create', help='Create agent')
    
    # channels
    channels_parser = subparsers.add_parser('channels', help='Manage channels')
    channels_sub = channels_parser.add_subparsers(dest='channels_command')
    channels_sub.add_parser('list', help='List channels')
    channels_sub.add_parser('add', help='Add channel')
    
    # up/down (docker compose wrappers)
    subparsers.add_parser('up', help='Start Prime')
    subparsers.add_parser('down', help='Stop Prime')
    subparsers.add_parser('restart', help='Restart Prime')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Docker compose shortcuts
    if args.command in ('up', 'down', 'restart'):
        os.chdir(PRIME_DIR)
        if args.command == 'up':
            subprocess.run(['docker', 'compose', 'up', '-d'])
        elif args.command == 'down':
            subprocess.run(['docker', 'compose', 'down'])
        elif args.command == 'restart':
            subprocess.run(['docker', 'compose', 'restart'])
        return 0
    
    # Route to command handlers
    commands = {
        'setup': cmd_setup,
        'doctor': cmd_doctor,
        'status': cmd_status,
        'logs': cmd_logs,
        'agents': cmd_agents,
        'channels': cmd_channels,
    }
    
    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
