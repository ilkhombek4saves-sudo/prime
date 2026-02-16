# Prime AI Agent - Безопасная Установка (White API)

Данное руководство описывает настройку сервера Prime с контролируемым исходящим доступом (egress). Сервер может обращаться только к разрешенным AI API, все остальные исходящие соединения блокируются.

## 🎯 Архитектура Безопасности

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ OpenAI  │ │Anthropic │ │ DeepSeek │ │ Telegram │           │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
└───────┼───────────┼────────────┼────────────┼─────────────────┘
        │           │            │            │
        └───────────┴──────┬─────┴────────────┘
                           │ HTTPS only
                           │ Whitelist filter
┌──────────────────────────┼─────────────────────────────────────┐
│                     EGRESS PROXY (Tinyproxy)                   │
│              • Domain whitelist filtering                       │
│              • Request logging                                  │
│              • Access control                                   │
└──────────────────────────┼─────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌────────▼────────┐  ┌──────▼───────┐
│  Backend     │  │ Browser Bridge  │  │  External    │
│  (FastAPI)   │  │  (Playwright)   │  │   Tools      │
└──────────────┘  └─────────────────┘  └──────────────┘
        │                  │
        └──────────────────┼──────────────────┘
                           │
              ┌────────────▼────────────┐
              │    Internal Network     │
              │      (no internet)      │
              │  ┌───────┐ ┌─────────┐ │
              │  │  DB   │ │  Redis  │ │
              │  │(PG)   │ │ (Cache) │ │
              │  └───┬───┘ └─────────┘ │
              └──────┼──────────────────┘
                     │
            ┌────────▼────────┐
            │  Caddy (HTTPS)  │
            │  Reverse Proxy  │
            └────────┬────────┘
                     │
              PUBLIC INTERNET
              (Users/Bots)
```

## 🚀 Быстрая Установка

### 1. Клонирование и запуск

```bash
# Клонируйте репозиторий
git clone <repo-url> /opt/prime
cd /opt/prime

# Запустите скрипт безопасной установки
sudo ./install-secure.sh
```

### 2. Ручная настройка (если нужно)

```bash
# Только firewall
sudo ./infrastructure/firewall/setup-iptables.sh

# Только Docker security
sudo ./install-secure.sh --skip-firewall
```

## 📋 Компоненты Безопасности

### 1. Egress Proxy (Tinyproxy)

**Расположение:** `infrastructure/egress/`

**Функции:**
- Фильтрация по доменам (whitelist)
- Логирование всех исходящих запросов
- Контроль доступа по IP

**Конфигурация:**
```bash
# Просмотр логов
sudo tail -f /var/log/tinyproxy/tinyproxy.log

# Редактирование whitelist
nano infrastructure/egress/whitelist.txt

# Перезапуск proxy
docker compose -f docker-compose.secure.yml restart egress-proxy
```

### 2. Firewall (UFW + iptables)

**Статус:**
```bash
# Просмотр статуса
sudo ufw status verbose
sudo iptables -L -v -n

# Логи блокировок
sudo tail -f /var/log/kern.log | grep PRIME
```

**Правила по умолчанию:**
- Весь входящий трафик: `DENY` (кроме 22, 80, 443)
- Весь исходящий трафик: `DENY` (кроме DNS, HTTPS к whitelist)
- Docker сети: полный доступ внутри

### 3. Docker Security

**Настройки:**
- `internal: true` сети для БД и Redis (нет интернета)
- `no-new-privileges` для всех контейнеров
- `cap_drop: ALL` + минимальные `cap_add`
- Non-root пользователи в контейнерах
- Read-only файловые системы где возможно

### 4. Network Isolation

```yaml
# Три изолированные сети:
internal-net:  # 172.28.1.0/24 - только внутри, NO internet
  internal: true
  
proxy-net:     # 172.28.2.0/24 - доступ к egress proxy

public-net:    # 172.28.3.0/24 - только для Caddy ingress
```

## 🔐 Whitelist Доменов

### AI API Провайдеры

| Провайдер | Домен | Порт | Описание |
|-----------|-------|------|----------|
| OpenAI | `api.openai.com` | 443 | GPT-4, GPT-3.5 |
| Anthropic | `api.anthropic.com` | 443 | Claude |
| DeepSeek | `api.deepseek.com` | 443 | DeepSeek Chat |
| Google | `generativelanguage.googleapis.com` | 443 | Gemini |
| Mistral | `api.mistral.ai` | 443 | Mistral AI |
| Cohere | `api.cohere.ai` | 443 | Cohere API |

### Бот API

| Платформа | Домен | Порт | Описание |
|-----------|-------|------|----------|
| Telegram | `api.telegram.org` | 443 | Bot API |
| Discord | `discord.com` | 443 | Gateway |
| Slack | `*.slack.com` | 443 | Slack API |

### Системные

| Сервис | Домен | Порт | Описание |
|--------|-------|------|----------|
| DNS | `1.1.1.1` | 53 | Cloudflare DNS |
| DNS | `8.8.8.8` | 53 | Google DNS |
| Time | `pool.ntp.org` | 123 | NTP |

### Добавление нового домена

```bash
# 1. Добавьте в whitelist
nano infrastructure/egress/whitelist.txt
# Добавьте: new-api.example.com

# 2. Перезапустите proxy
docker compose -f docker-compose.secure.yml restart egress-proxy

# 3. Добавьте в firewall (если strict mode)
sudo iptables -A OUTPUT -p tcp -d new-api.example.com --dport 443 -j ACCEPT
```

## 📊 Мониторинг

### Логи Egress

```bash
# Все исходящие запросы
sudo docker compose -f docker-compose.secure.yml logs -f egress-proxy

# Только заблокированные (измените LogLevel в tinyproxy.conf)
grep "DENIED" /var/log/tinyproxy/tinyproxy.log
```

### Статистика

```bash
# Активные соединения
sudo ss -tuln | grep 8888

# Docker сети
docker network ls
docker network inspect prime_internal-net

# Контейнеры
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Алерты

```bash
# Проверка на необычную активность
sudo tail -f /var/log/kern.log | grep -E "(PRIME-EGRESS-BLOCKED|PRIME-HTTPS-BLOCKED)"
```

## 🔧 Управление

### Запуск

```bash
# Полный запуск
cd /opt/prime
sudo docker compose -f docker-compose.secure.yml up -d

# Сборка и запуск
sudo docker compose -f docker-compose.secure.yml up -d --build
```

### Остановка

```bash
# Мягкая остановка
sudo docker compose -f docker-compose.secure.yml down

# Полная остановка с удалением volumes (осторожно!)
sudo docker compose -f docker-compose.secure.yml down -v
```

### Обновление

```bash
# Обновление кода
git pull

# Пересборка
sudo docker compose -f docker-compose.secure.yml build --no-cache

# Перезапуск
sudo docker compose -f docker-compose.secure.yml up -d
```

## 🛡️ Hardening Рекомендации

### 1. SSH

```bash
# Отключить root login
sudo sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config

# Отключить password auth
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Изменить порт (опционально)
sudo sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config

sudo systemctl restart sshd
```

### 2. Автоматические Обновления

```bash
# Установка unattended-upgrades
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 3. Fail2Ban

```bash
# Статус
sudo fail2ban-client status

# Бан IP вручную
sudo fail2ban-client set sshd banip 1.2.3.4

# Разбан
sudo fail2ban-client set sshd unbanip 1.2.3.4
```

### 4. Аудит Безопасности

```bash
# Установка Lynis
sudo apt install -y lynis

# Запуск аудита
sudo lynis audit system
```

## 🚨 Troubleshooting

### API не работает

```bash
# Проверьте whitelist
grep "api.example.com" infrastructure/egress/whitelist.txt

# Проверьте логи proxy
docker compose -f docker-compose.secure.yml logs egress-proxy

# Проверьте DNS
nslookup api.openai.com

# Тест из контейнера
docker compose -f docker-compose.secure.yml exec backend \
    curl -x http://egress-proxy:8888 https://api.openai.com/v1/models \
    -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Firewall блокирует легитимный трафик

```bash
# Временно отключить строгий egress (осторожно!)
sudo iptables -F OUTPUT
sudo iptables -P OUTPUT ACCEPT

# Или добавить правило для конкретного IP
sudo iptables -I OUTPUT -p tcp -d API_IP --dport 443 -j ACCEPT
```

### Контейнер не имеет интернета

```bash
# Проверка сети
docker compose -f docker-compose.secure.yml exec backend \
    curl -I https://api.openai.com

# Должно работать через proxy
docker compose -f docker-compose.secure.yml exec backend \
    env | grep PROXY
# Должно показать:
# HTTP_PROXY=http://egress-proxy:8888
# HTTPS_PROXY=http://egress-proxy:8888
```

## 📚 Дополнительные Ресурсы

- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [OWASP Container Security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)

---

**Версия:** 1.0  
**Обновлено:** 2026-02-15  
**Статус:** Production Ready ✅
