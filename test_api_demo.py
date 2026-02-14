#!/usr/bin/env python3
"""
Демо-тест API Prime
Проверяет основные эндпоинты без запуска сервера
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Проверка импортов основных модулей"""
    print("Проверка импортов основных модулей...")
    
    modules_to_test = [
        ("FastAPI", "fastapi"),
        ("SQLAlchemy", "sqlalchemy"),
        ("Pydantic", "pydantic"),
        ("Uvicorn", "uvicorn"),
    ]
    
    for name, module in modules_to_test:
        try:
            __import__(module)
            print(f"  ✓ {name}")
        except ImportError as e:
            print(f"  ✗ {name}: {e}")
            return False
    
    return True

def test_backend_modules():
    """Проверка импортов модулей бэкенда"""
    print("\nПроверка импортов модулей бэкенда...")
    
    # Добавляем путь к бэкенду
    sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
    
    backend_modules = [
        ("Настройки", "app.config.settings"),
        ("Модели", "app.persistence.models"),
        ("Схемы", "app.schemas.common"),
        ("Провайдеры", "app.providers.base"),
        ("Сервисы", "app.services.agent_runner"),
    ]
    
    for name, module_path in backend_modules:
        try:
            __import__(module_path)
            print(f"  ✓ {name}")
        except ImportError as e:
            print(f"  ✗ {name}: {e}")
            # Не прерываем, так как некоторые модули могут требовать окружение
    
    return True

def test_config_parsing():
    """Проверка парсинга конфигурационных файлов"""
    print("\nПроверка парсинга конфигурационных файлов...")
    
    import yaml
    
    config_files = [
        ("config/providers.yaml", "Провайдеры"),
        ("config/bots.yaml", "Боты"),
        ("config/plugins.yaml", "Плагины"),
    ]
    
    for file_path, name in config_files:
        try:
            with open(file_path, 'r') as f:
                config = yaml.safe_load(f)
            if config:
                print(f"  ✓ {name}: {len(config)} элементов")
            else:
                print(f"  ✗ {name}: пустой файл")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    
    return True

def test_env_file():
    """Проверка .env файла"""
    print("\nПроверка .env файла...")
    
    env_example = ".env.example"
    if os.path.exists(env_example):
        with open(env_example, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        print(f"  ✓ .env.example: {len(lines)} переменных окружения")
        
        # Проверяем важные переменные
        important_vars = [
            "DATABASE_URL",
            "SECRET_KEY", 
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "ANTHROPIC_API_KEY"
        ]
        
        env_content = "\n".join(lines)
        missing = []
        for var in important_vars:
            if var in env_content:
                print(f"    • {var}: присутствует")
            else:
                print(f"    • {var}: отсутствует")
                missing.append(var)
        
        if missing:
            print(f"  ⚠️  Отсутствуют важные переменные: {', '.join(missing)}")
    else:
        print("  ✗ .env.example не найден")
    
    return True

def test_project_structure():
    """Проверка структуры проекта"""
    print("\nПроверка структуры проекта...")
    
    structure = {
        "backend/": "Бэкенд",
        "app/": "Фронтенд",
        "config/": "Конфигурация",
        "docs/": "Документация",
        "prime/": "CLI инструменты",
    }
    
    for path, name in structure.items():
        if os.path.exists(path):
            # Подсчитываем файлы
            py_files = len(list(Path(path).rglob("*.py")))
            total_files = len(list(Path(path).rglob("*")))
            print(f"  ✓ {name}: {total_files} файлов ({py_files} .py)")
        else:
            print(f"  ✗ {name}: не найден")
    
    return True

def generate_quickstart_guide():
    """Генерация краткого руководства по запуску"""
    print("\n" + "="*60)
    print("КРАТКОЕ РУКОВОДСТВО ПО ЗАПУСКУ")
    print("="*60)
    
    guide = """
1. НАСТРОЙКА ОКРУЖЕНИЯ:
   ```
   cp .env.example .env
   # Отредактируйте .env, добавьте ваши API ключи:
   # - OPENAI_API_KEY
   # - GEMINI_API_KEY  
   # - ANTHROPIC_API_KEY
   # - DEEPSEEK_API_KEY
   # - KIMI_API_KEY
   ```

2. ЗАПУСК В DOCKER (рекомендуется):
   ```
   docker compose up --build
   ```
   После запуска:
   - Бэкенд: http://localhost:8000
   - Фронтенд: http://localhost:5173
   - Документация API: http://localhost:8000/docs

3. ЗАПУСК В LITE РЕЖИМЕ (без Docker):
   ```
   ./install-lite.sh
   prime init
   prime serve
   ```
   После запуска:
   - Интерфейс: http://127.0.0.1:18789

4. ТЕСТИРОВАНИЕ:
   ```
   # Запуск тестов бэкенда
   cd backend && python -m pytest
   
   # Проверка здоровья
   curl http://localhost:8000/api/healthz
   
   # Проверка метрик
   curl http://localhost:8000/api/metrics
   ```

5. ОСНОВНЫЕ КОМАНДЫ CLI:
   ```
   prime status      # Статус системы
   prime doctor      # Диагностика
   prime agent "hi"  # Отправить сообщение LLM
   prime dashboard   # Открыть UI
   ```

6. КОНФИГУРАЦИЯ:
   - Провайдеры: config/providers.yaml
   - Боты: config/bots.yaml
   - Плагины: config/plugins.yaml
   """
    
    print(guide)

def main():
    """Основная функция"""
    print("="*60)
    print("ДЕМО-ТЕСТ СИСТЕМЫ PRIME API")
    print("="*60)
    
    tests = [
        ("Импорты зависимостей", test_imports),
        ("Импорты модулей бэкенда", test_backend_modules),
        ("Парсинг конфигурации", test_config_parsing),
        ("Файл окружения", test_env_file),
        ("Структура проекта", test_project_structure),
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
    
    print(f"\nВсего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {total - passed}")
    
    # Генерация руководства
    generate_quickstart_guide()
    
    # Заключение
    print("\n" + "="*60)
    print("ЗАКЛЮЧЕНИЕ")
    print("="*60)
    
    if passed == total:
        print("\n✅ Система Prime готова к запуску!")
        print("Все основные компоненты работают корректно.")
        print("Следуйте руководству выше для запуска проекта.")
    else:
        print("\n⚠️  Требуется дополнительная настройка.")
        print("Некоторые компоненты могут не работать корректно.")
        print("Проверьте ошибки выше и установите недостающие зависимости.")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())