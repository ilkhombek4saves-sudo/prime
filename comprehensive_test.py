#!/usr/bin/env python3
"""
Комплексный тест проекта Prime
Проверяет все основные компоненты системы
"""

import sys
import os
import subprocess
import json
from pathlib import Path

def run_command(cmd, cwd=None):
    """Выполнить команду и вернуть результат"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def test_backend():
    """Тестирование бэкенда"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ БЭКЕНДА")
    print("="*60)
    
    tests = []
    
    # 1. Проверка импортов
    print("\n1. Проверка импортов бэкенда...")
    success, stdout, stderr = run_command(
        "python3 -c 'from app.main import app; print(\"✓ FastAPI app loaded\")'",
        cwd="backend"
    )
    if success:
        print("   ✓ Импорты работают")
        tests.append(("Импорты бэкенда", True))
    else:
        print(f"   ✗ Ошибка импорта: {stderr}")
        tests.append(("Импорты бэкенда", False))
    
    # 2. Запуск тестов
    print("\n2. Запуск unit-тестов...")
    success, stdout, stderr = run_command(
        "python3 -m pytest -v -k 'not integration' --tb=short",
        cwd="backend"
    )
    if success:
        print("   ✓ Unit-тесты прошли успешно")
        tests.append(("Unit-тесты", True))
    else:
        print(f"   ✗ Unit-тесты упали: {stderr[:500]}")
        tests.append(("Unit-тесты", False))
    
    # 3. Проверка конфигурации
    print("\n3. Проверка конфигурационных файлов...")
    config_files = [
        ("config/providers.yaml", "providers.yaml"),
        ("config/bots.yaml", "bots.yaml"),
        ("config/plugins.yaml", "plugins.yaml"),
    ]
    
    for file_path, name in config_files:
        if os.path.exists(file_path):
            print(f"   ✓ {name} найден")
            tests.append((f"Конфиг {name}", True))
        else:
            print(f"   ✗ {name} не найден")
            tests.append((f"Конфиг {name}", False))
    
    return tests

def test_frontend():
    """Тестирование фронтенда"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ФРОНТЕНДА")
    print("="*60)
    
    tests = []
    
    # 1. Проверка package.json
    print("\n1. Проверка package.json...")
    if os.path.exists("app/package.json"):
        print("   ✓ package.json найден")
        tests.append(("package.json", True))
    else:
        print("   ✗ package.json не найден")
        tests.append(("package.json", False))
    
    # 2. Проверка node_modules
    print("\n2. Проверка node_modules...")
    if os.path.exists("app/node_modules"):
        print("   ✓ node_modules установлены")
        tests.append(("node_modules", True))
    else:
        print("   ✗ node_modules не установлены")
        tests.append(("node_modules", False))
    
    # 3. Проверка сборки
    print("\n3. Проверка сборки фронтенда...")
    success, stdout, stderr = run_command("npm run build", cwd="app")
    if success:
        print("   ✓ Фронтенд успешно собирается")
        tests.append(("Сборка фронтенда", True))
    else:
        print(f"   ✗ Ошибка сборки: {stderr[:500]}")
        tests.append(("Сборка фронтенда", False))
    
    # 4. Проверка dist директории
    print("\n4. Проверка собранных файлов...")
    if os.path.exists("app/dist"):
        dist_files = list(Path("app/dist").rglob("*"))
        if dist_files:
            print(f"   ✓ Собрано {len(dist_files)} файлов")
            tests.append(("Собранные файлы", True))
        else:
            print("   ✗ Директория dist пуста")
            tests.append(("Собранные файлы", False))
    else:
        print("   ✗ Директория dist не создана")
        tests.append(("Собранные файлы", False))
    
    return tests

def test_docker():
    """Тестирование Docker конфигурации"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ DOCKER КОНФИГУРАЦИИ")
    print("="*60)
    
    tests = []
    
    # 1. Проверка Docker Compose файлов
    print("\n1. Проверка Docker Compose файлов...")
    docker_files = [
        ("docker-compose.yml", "Основной docker-compose"),
        ("docker-compose.prod.yml", "Продакшен docker-compose"),
        ("backend/Dockerfile", "Dockerfile бэкенда"),
        ("app/Dockerfile", "Dockerfile фронтенда"),
        ("app/Dockerfile.prod", "Dockerfile фронтенда (prod)"),
    ]
    
    for file_path, name in docker_files:
        if os.path.exists(file_path):
            print(f"   ✓ {name} найден")
            tests.append((name, True))
        else:
            print(f"   ✗ {name} не найден")
            tests.append((name, False))
    
    # 2. Проверка Docker установки
    print("\n2. Проверка установки Docker...")
    success, stdout, stderr = run_command("docker --version")
    if success:
        print(f"   ✓ Docker установлен: {stdout.strip()}")
        tests.append(("Docker установлен", True))
    else:
        print("   ✗ Docker не установлен")
        tests.append(("Docker установлен", False))
    
    # 3. Проверка Docker Compose
    print("\n3. Проверка Docker Compose...")
    success, stdout, stderr = run_command("docker compose version")
    if success:
        print(f"   ✓ Docker Compose установлен: {stdout.strip()}")
        tests.append(("Docker Compose", True))
    else:
        print("   ✗ Docker Compose не установлен")
        tests.append(("Docker Compose", False))
    
    return tests

def test_cli():
    """Тестирование CLI инструментов"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ CLI ИНСТРУМЕНТОВ")
    print("="*60)
    
    tests = []
    
    # 1. Проверка Makefile
    print("\n1. Проверка Makefile...")
    if os.path.exists("Makefile"):
        print("   ✓ Makefile найден")
        tests.append(("Makefile", True))
        
        # Проверка доступных команд
        success, stdout, stderr = run_command("make help")
        if success:
            print("   ✓ Makefile команды работают")
            tests.append(("Makefile команды", True))
        else:
            print("   ✗ Makefile команды не работают")
            tests.append(("Makefile команды", False))
    else:
        print("   ✗ Makefile не найден")
        tests.append(("Makefile", False))
    
    # 2. Проверка скриптов установки
    print("\n2. Проверка скриптов установки...")
    install_scripts = [
        ("install-lite.sh", "Lite установщик"),
        ("deploy.sh", "Скрипт деплоя"),
    ]
    
    for file_path, name in install_scripts:
        if os.path.exists(file_path):
            print(f"   ✓ {name} найден")
            tests.append((name, True))
        else:
            print(f"   ✗ {name} не найден")
            tests.append((name, False))
    
    # 3. Проверка основного CLI скрипта
    print("\n3. Проверка основного CLI...")
    if os.path.exists("prime"):
        print("   ✓ Основной CLI скрипт найден")
        tests.append(("Основной CLI", True))
        
        # Проверка прав
        success, stdout, stderr = run_command("ls -la prime | head -1")
        if success and "x" in stdout:
            print("   ✓ CLI скрипт исполняемый")
            tests.append(("CLI исполняемый", True))
        else:
            print("   ✗ CLI скрипт не исполняемый")
            tests.append(("CLI исполняемый", False))
    else:
        print("   ✗ Основной CLI скрипт не найден")
        tests.append(("Основной CLI", False))
    
    return tests

def test_documentation():
    """Тестирование документации"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ДОКУМЕНТАЦИИ")
    print("="*60)
    
    tests = []
    
    # 1. Проверка основных файлов документации
    print("\n1. Проверка документации...")
    doc_files = [
        ("README.md", "Основной README"),
        ("LITE_MODE.md", "Документация Lite режима"),
        ("CONTRIBUTING.md", "Руководство по вкладу"),
        ("docs/PRODUCT_FLOW.md", "Описание продукта"),
        ("docs/ROADMAP.md", "Дорожная карта"),
    ]
    
    for file_path, name in doc_files:
        if os.path.exists(file_path):
            print(f"   ✓ {name} найден")
            tests.append((name, True))
        else:
            print(f"   ✗ {name} не найден")
            tests.append((name, False))
    
    return tests

def main():
    """Основная функция тестирования"""
    print("\n" + "="*60)
    print("КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ ПРОЕКТА PRIME")
    print("="*60)
    
    all_tests = []
    
    # Запуск всех тестов
    all_tests.extend(test_backend())
    all_tests.extend(test_frontend())
    all_tests.extend(test_docker())
    all_tests.extend(test_cli())
    all_tests.extend(test_documentation())
    
    # Вывод итогов
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    passed = sum(1 for _, success in all_tests if success)
    total = len(all_tests)
    
    print(f"\nВсего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {total - passed}")
    print(f"Успешность: {passed/total*100:.1f}%")
    
    # Детальный вывод
    print("\nДетальные результаты:")
    for name, success in all_tests:
        status = "✓" if success else "✗"
        print(f"  {status} {name}")
    
    # Рекомендации
    print("\n" + "="*60)
    print("РЕКОМЕНДАЦИИ")
    print("="*60)
    
    if passed == total:
        print("\n✅ Все тесты пройдены успешно!")
        print("Проект Prime готов к использованию.")
        print("\nСледующие шаги:")
        print("1. Настройте .env файл (скопируйте из .env.example)")
        print("2. Запустите: docker compose up --build")
        print("3. Или используйте Lite режим: ./install-lite.sh")
    else:
        print("\n⚠️  Некоторые тесты провалились.")
        print("\nРекомендуемые действия:")
        print("1. Установите недостающие зависимости")
        print("2. Проверьте права доступа к файлам")
        print("3. Запустите тесты снова после исправлений")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())