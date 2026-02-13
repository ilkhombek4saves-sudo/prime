# Operations

## Deploy
- Use `docker-compose up --build` for non-production.
- For production, build immutable images and deploy with environment-specific secrets.

## Observability
- Scrape `/api/metrics` with Prometheus.
- Forward JSON logs to centralized log storage.

## Backups
- Backup PostgreSQL volume and S3/R2 artifacts.
