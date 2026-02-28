# MimmiFlowers — Deployment Guide

## Architecture Overview

```
Internet → Nginx (client container, port 80/443)
               ├── Static files → served directly
               └── /api/* → proxy_pass → FastAPI (server container, port 8000)
                                              └── PostgreSQL (db container, port 5432)
```

Three Docker containers orchestrated via `docker-compose`:
- **client** — Nginx serving the React build + reverse-proxying API requests
- **server** — Gunicorn + Uvicorn workers running FastAPI
- **db** — PostgreSQL 16

---

## Prerequisites

- Docker and Docker Compose v2+
- A domain name pointing to your server (e.g. `mimmiflowers.se`)
- SSL certificates (Let's Encrypt recommended)
- Stripe account with live API keys

---

## Environment Variables

The server reads all configuration from environment variables. The `ENV` variable
controls which `.env` file is loaded:

| `ENV` value | File loaded  | Purpose     |
|-------------|-------------|-------------|
| `dev`       | `.env.dev`  | Local dev   |
| `stg`       | `.env.stg`  | Staging     |
| `prod`      | `.env.prod` | Production  |

### Required variables (server)

| Variable                | Description                                        |
|-------------------------|----------------------------------------------------|
| `DB_URL`                | PostgreSQL connection string                       |
| `STRIPE_SECRET_KEY`     | Stripe secret key (`sk_live_...` for prod)         |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_...`)        |
| `SUCCESS_URL`           | URL Stripe redirects to on success                 |
| `CANCEL_URL`            | URL Stripe redirects to on cancel                  |
| `ZOHO_SMTP_HOST`        | SMTP server hostname                               |
| `ZOHO_SMTP_PORT`        | SMTP server port (typically `587`)                 |
| `ZOHO_SMTP_USER`        | SMTP login email                                   |
| `ZOHO_SMTP_PASSWORD`    | SMTP login password                                |
| `ZOHO_SMTP_SENDER_NAME` | Display name for outgoing emails                  |

### Optional variables

| Variable       | Default                | Description                          |
|----------------|------------------------|--------------------------------------|
| `CORS_ORIGINS` | Per-environment default | Comma-separated allowed CORS origins |

### Required variables (client build)

Set these as build args or in the CI environment:

| Variable              | Description                     |
|-----------------------|---------------------------------|
| `VITE_API_URL`        | Base URL for the API server     |
| `VITE_STRIPE_PUBLIC_KEY` | Stripe publishable key       |

---

## Local Development

```bash
# From the server/ directory:
docker compose up --build
```

This starts all three services:
- Client at http://localhost:3000
- Server at http://localhost:8000
- PostgreSQL at localhost:5432

The dev compose file uses `.env.dev` and seeds the database from `db/init/`.

---

## Production Deployment

### 1. Prepare the server

```bash
# SSH into your EC2 instance
ssh user@your-server

# Clone repositories (or pull latest)
git clone <client-repo> client
git clone <server-repo> server
git clone <db-repo> db
```

### 2. Configure environment

```bash
# Create production env file
cp server/.env.dev server/.env.prod
# Edit with real production values
nano server/.env.prod
```

### 3. Set up SSL (first time only)

```bash
# Install certbot
sudo apt install certbot

# Obtain certificates
sudo certbot certonly --standalone -d mimmiflowers.se -d www.mimmiflowers.se

# Certificates will be at /etc/letsencrypt/live/mimmiflowers.se/
```

### 4. Configure Nginx for SSL

Update the client's `nginx.conf` to include SSL configuration:

```nginx
server {
    listen 443 ssl;
    server_name mimmiflowers.se www.mimmiflowers.se;

    ssl_certificate     /etc/letsencrypt/live/mimmiflowers.se/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mimmiflowers.se/privkey.pem;

    # ... existing location blocks ...

    location /api/ {
        proxy_pass http://server:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name mimmiflowers.se www.mimmiflowers.se;
    return 301 https://$host$request_uri;
}
```

### 5. Deploy

```bash
# From the server/ directory:
docker compose -f docker-compose.prod.yml up -d --build
```

### 6. Verify

```bash
# Check all containers are running
docker compose -f docker-compose.prod.yml ps

# Check health endpoint
curl -s https://mimmiflowers.se/api/health | jq .

# Check logs
docker compose -f docker-compose.prod.yml logs -f server
```

---

## Database Migrations

Migrations are managed with Alembic.

```bash
# Run inside the server container:
docker compose exec server alembic upgrade head

# Or locally with venv:
cd server
venv/bin/python -m alembic upgrade head
```

---

## Updating

```bash
# Pull latest code
git pull origin main    # in each repo

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build

# Run any new migrations
docker compose -f docker-compose.prod.yml exec server alembic upgrade head
```

---

## Monitoring

### Health check

The server exposes `GET /health` which verifies DB connectivity and returns
`200 OK` or `503 Service Unavailable`. Use this for uptime monitoring.

### Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Server only
docker compose -f docker-compose.prod.yml logs -f server
```

### Recommended monitoring tools

- **Uptime**: UptimeRobot, Pingdom, or similar — poll `GET /health` every 60s
- **Error tracking**: Sentry (client + server) — captures unhandled exceptions with stack traces
- **Log aggregation**: CloudWatch (if on AWS) or Loki + Grafana

### Setting up Sentry (optional)

**Client:**
```bash
npm install @sentry/react
```
```typescript
// src/main.tsx
import * as Sentry from "@sentry/react";
Sentry.init({ dsn: "https://your-dsn@sentry.io/project-id" });
```

**Server:**
```bash
pip install sentry-sdk[fastapi]
```
```python
# main.py
import sentry_sdk
sentry_sdk.init(dsn="https://your-dsn@sentry.io/project-id")
```

---

## CI/CD

GitHub Actions workflows are in `.github/workflows/ci.yml` in both repos.

**Server pipeline:** Install Python deps → Run pytest

**Client pipeline:** Install Node deps → Lint → Type check → Test → Build

These run on pushes to `main` and `AgentProdFixedVersion`, and on PRs to `main`.

---

## Rollback

```bash
# Roll back to previous version
git checkout <previous-commit>
docker compose -f docker-compose.prod.yml up -d --build

# Roll back database migration
docker compose -f docker-compose.prod.yml exec server alembic downgrade -1
```

---

## Security Checklist

- [ ] `.env.prod` contains live Stripe keys (not test keys)
- [ ] `.env.prod` is NOT committed to git
- [ ] SSL certificates are valid and auto-renewing
- [ ] Stripe webhook endpoint is configured for the production URL
- [ ] CORS origins are set to production domains only
- [ ] `/docs` and `/redoc` are disabled in production (automatic when `ENV=prod`)
- [ ] Database password is strong and unique
- [ ] Server runs as non-root user (configured in Dockerfile)
