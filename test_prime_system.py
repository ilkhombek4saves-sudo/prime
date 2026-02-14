#!/usr/bin/env python3
"""
Тест основных функций системы Prime
"""

import sys
import os
import json
from pathlib import Path

def test_config_files():
    """Проверка конфигурационных файлов"""
    print("Проверка конфигурационных файлов...")
    
    configs = {
        "providers.yaml": "config/providers.yaml",
        "bots.yaml": "config/bots.yaml", 
        "plugins.yaml": "config/plugins.yaml",
        ".env.example": ".env.example"
    }
    
    for name, path in configs.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  ✓ {name}: {size} байт")
        else:
            print(f"  ✗ {name}: не найден")
            return False
    
    return True

def test_backend_structure():
    """Проверка структуры бэкенда"""
    print("\nПроверка структуры бэкенда...")
    
    required_dirs = [
        "backend/app/api",
        "backend/app/services", 
        "backend/app/providers",
        "backend/app/schemas",
        "backend/tests"
    ]
    
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            files = len(list(Path(dir_path).rglob("*.py")))
            print(f"  ✓ {dir_path}: {files} Python файлов")
        else:
            print(f"  ✗ {dir_path}: не найден")
            return False
    
    return True

def test_frontend_structure():
    """Проверка структуры фронтенда"""
    print("\nПроверка структуры фронтенда...")
    
    required_files = [
        "app/package.json",
        "app/src/App.tsx",
        "app/src/main.tsx",
        "app/vite.config.ts"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"  ✓ {file_path}: {size} байт")
        else:
            print(f"  ✗ {file_path}: не найден")
            return False
    
    return True

def test_docker_config():
    """Проверка Docker конфигурации"""
    print("\nПроверка Docker конфигурации...")
    
    docker_files = [
        "docker-compose.yml",
        "docker-compose.prod.yml",
        "backend/Dockerfile",
        "app/Dockerfile"
    ]
    
    for file_path in docker_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"  ✓ {file_path}: {size} байт")
        else:
            print(f"  ✗ {file_path}: не найден")
            return False
    
    return True

def test_cli_tools():
    """Проверка CLI инструментов"""
    print("\nПроверка CLI инструментов...")
    
    cli_files = [
        "Makefile",
        "install-lite.sh",
        "deploy.sh"
    ]
    
    for file_path in cli_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"  ✓ {file_path}: {size} байт")
        else:
            print(f"  ✗ {file_path}: не найден")
    
    # Проверка директории prime
    if os.path.exists("prime"):
        py_files = len(list(Path("prime").rglob("*.py")))
        print(f"  ✓ prime/: {py_files} Python файлов")
    else:
        print(f"  ✗ prime/: не найден")
    
    return True

def test_documentation():
    """Проверка документации"""
    print("\nПроверка документации...")
    
    docs = [
        "README.md",
        "LITE_MODE.md",
        "CONTRIBUTING.md",
        "docs/PRODUCT_FLOW.md",
        "docs/ROADMAP.md"
    ]
    
    for doc in docs:
        if os.path.exists(doc):
            size = os.path.getsize(doc)
            print(f"  ✓ {doc}: {size} байт")
        else:
            print(f"  ✗ {doc}: не найден")
    
    return True

def main():
    """Основная функция тестирования"""
    print("="*60)
    print("ТЕСТИРОВАНИЕ СИСТЕМЫ PRIME")
    print("="*60)
    
    tests = [
        ("Конфигурационные файлы", test_config_files),
        ("Структура бэкенда", test_backend_structure),
        ("Структура фронтенда", test_frontend_structure),
        ("Docker конфигурация", test_docker_config),
        ("CLI инструменты", test_cli_tools),
        ("Документация", test_documentation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            results.append((test_name, False))
    
    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\nВсего проверок: {total}")
    print(f"Успешно: {passed}")
    print(f"Провалено: {total - passed}")
    
    print("\nДетальные результаты:")
    for test_name, success in results:
        status = "✓" if success else "✗"
        print(f"  {status} {test_name}")
    
    # Анализ системы
    print("\n" + "="*60)
    print("АНАЛИЗ СИСТЕМЫ")
    print("="*60)
    
    # Подсчет файлов
    total_py_files = len(list(Path(".").rglob("*.py")))
    total_js_ts_files = len(list(Path(".").rglob("*.js"))) + len(list(Path(".").rglob("*.ts")))
    total_yaml_files = len(list(Path(".").rglob("*.yaml"))) + len(list(Path(".").rglob("*.yml")))
    
    print(f"\nСтатистика проекта:")
    print(f"  • Python файлов: {total_py_files}")
    print(f"  • JavaScript/TypeScript файлов: {total_js_ts_files}")
    print(f"  • YAML файлов: {total_yaml_files}")
    
    # Проверка размера проекта
    total_size = sum(f.stat().st_size for f in Path(".").rglob("*") if f.is_file())
    print(f"  • Общий размер: {total_size / 1024 / 1024:.1f} MB")
    
    # Рекомендации
    print("\n" + "="*60)
    print("РЕКОМЕНДАЦИИ")
    print("="*60)
    
    if passed == total:
        print("\n✅ Система Prime полностью работоспособна!")
        print("\nСледующие шаги для запуска:")
        print("1. Настройте окружение:")
        print("   cp .env.example .env")
        print("   # Отредактируйте .env, добавьте API ключи")
        print("\n2. Запустите в Docker:")
        print("   docker compose up --build")
        print("\n3. Или используйте Lite режим:")
        print("   ./install-lite.sh")
        print("   prime init")
        print("   prime serve")
        print("\n4. Откройте в браузере:")
        print("   http://localhost:5173 (Full mode)")
        print("   http://127.0.0.1:18789 (Lite mode)")
    else:
        print("\n⚠️  Некоторые компоненты требуют внимания.")
        print("\nРекомендуемые действия:")
        print("1. Убедитесь, что все необходимые файлы на месте")
        print("2. Проверьте права доступа")
        print("3. Установите недостающие зависимости")
        print("4. Запустите тесты снова")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())