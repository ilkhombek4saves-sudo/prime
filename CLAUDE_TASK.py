#!/usr/bin/env python3
"""
TASK FOR CLAUDE AGENT - Prime Project Refactoring
Run this task with: prime "$(cat /home/ilkhombek4saves/prime/CLAUDE_TASK.md)"
"""

TASK = """
Ты получил задание от Эмана исправить проект Prime полностью.

## Контекст
Проект Prime — AI-ассистент как OpenClaw.ai, но сейчас не работает корректно.
Репозиторий: /home/ilkhombek4saves/prime

## API Keys для тестирования:
```
DEEPSEEK_API_KEY=sk-85f89945161646beb062d578f1974581
ANTHROPIC_API_KEY=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
```

## Проблемы которые нужно исправить:

### 1. Структура проекта (критично)
Сейчас есть дублирование:
- `lite/prime-lite.py` — основной файл (~1000 строк, монолит)
- `lite/prime-lite-v2.py` — рефакторинг с модулями
- `lite/scanner.py`, `resilience.py`, `selfaware.py` — модули

Нужно:
- Оставить ОДИН рабочий вариант
- Использовать модульную структуру (v2) как основу
- Сделать симлинк `prime -> lite/prime-lite.py` рабочим

### 2. Tool Calling (критично)
Модель (Qwen/Ollama) иногда отвечает текстом вместо вызова tools:
- "Я не могу получить доступ к файловой системе"
- "Я текстовый AI-ассистент"

Нужно:
- Усилить системный промпт (CRITICAL: YOU MUST USE TOOLS)
- Добавить fallback: если модель отказывается, принудительно требовать tool
- Проверить формат tool_definitions для Ollama

### 3. Fast Paths
Добавить быстрые пути без LLM:
- `prime ls` -> direct subprocess
- `prime "read README.md"` -> direct file read
- `prime scan` -> project scanner
- `prime status` -> system info

### 4. Smart Routing
- simple -> local Ollama
- code -> Claude (ANTHROPIC_API_KEY)
- complex -> DeepSeek или ensemble
- Retry logic с fallback на Ollama

### 5. CLI Команды
- `prime status` — статус системы
- `prime whoami` — информация об окружении  
- `prime scan` — сканирование проектов
- `prime init` — инициализация
- `prime ls` — быстрый ls
- `prime "query"` — запрос к агенту

### 6. Интерактивный режим
- Сохранение контекста между сообщениями
- История разговора
- Выход по 'exit' или Ctrl+C

## Чеклист перед завершением:
- [ ] `prime status` — показывает всё корректно
- [ ] `prime ls` — мгновенный вывод файлов
- [ ] `prime scan` — находит проекты
- [ ] `prime "What files are here?"` — вызывает tools (не говорит что не может)
- [ ] `prime "Read README.md"` — читает файл
- [ ] Интерактивный режим работает
- [ ] git commit с сообщением о рефакторинге

## Начни с:
1. Анализа текущего состояния: `ls -la /home/ilkhombek4saves/prime`
2. Проверки какой файл сейчас используется: `cat /home/ilkhombek4saves/prime/prime`
3. Рефакторинга структуры
4. Тестирования каждой команды
"""

if __name__ == "__main__":
    print(TASK)
