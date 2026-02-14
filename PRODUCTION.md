# Prime Production Deployment Guide

## Quick Deploy

```bash
# 1. Clone repo
git clone https://github.com/yourusername/prime.git
cd prime

# 2. Configure
# Edit .env with your domain and API keys
cp .env.example .env
nano .env

# 3. Deploy
./deploy.sh your-domain.com your-email@example.com
```

## Requirements

- Docker + Docker Compose v2
- 2GB RAM minimum (4GB recommended)
- 10GB disk space
- Domain name (optional, for HTTPS)

## Configuration

Edit `.env`:

```bash
# Required
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -base64 32)

# Domain for HTTPS
DOMAIN=prime.yourdomain.com
EMAIL=admin@yourdomain.com

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_AUTH_TOKEN=sk-ant-...
```

## HTTPS

Caddy автоматически получит SSL сертификат от Let's Encrypt.

Для локального теста используется self-signed сертификат.

## Monitoring

```bash
# Status
docker compose -f docker-compose.prod.yml ps

# Logs
docker compose -f docker-compose.prod.yml logs -f

# Metrics
curl http://localhost/api/metrics
```

## Backup

```bash
# Manual backup
./backup.sh

# Automated (включено в docker-compose.prod.yml)
# Бэкапы каждый день в 2:00 AM, хранятся 7 дней
```

## Update

```bash
# Pull latest
git pull

# Redeploy
./deploy.sh
```

## Troubleshooting

### Services not starting

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs backend

# Check disk space
df -h

# Restart
docker compose -f docker-compose.prod.yml restart
```

### Database connection issues

```bash
# Check DB health
docker compose -f docker-compose.prod.yml ps db

# Connect manually
docker compose -f docker-compose.prod.yml exec db psql -U prime -d prime
```

### HTTPS not working

```bash
# Check Caddy logs
docker compose -f docker-compose.prod.yml logs caddy

# Verify domain DNS points to server
nslookup your-domain.com
```

## Security Checklist

- [ ] Changed all default passwords in `.env`
- [ ] Restricted `.env` permissions: `chmod 600 .env`
- [ ] Configured firewall (ports 80, 443, 22)
- [ ] Disabled root SSH login
- [ ] Enabled automatic security updates
- [ ] Set up monitoring/alerts
- [ ] Regular backups tested
