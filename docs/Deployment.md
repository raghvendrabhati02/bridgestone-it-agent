# Deployment Guide

> **Project:** Bridgestone IT AI Assistant · **Last updated:** 2026-07-26

---

## Prerequisites

| Requirement | Minimum version | Purpose |
|---|---|---|
| Python | 3.12 | Backend runtime |
| Node.js | 20 | Frontend build and dev server |
| npm | 9 | Package management |
| Docker | 24 | Container deployment |
| Docker Compose | 2 (v2 syntax) | Service orchestration |
| Git | Any | Source control |

---

## Local Development (without Docker)

### 1. Clone the repository

```bash
git clone https://github.com/your-org/bridgestone-it-agent.git
cd bridgestone-it-agent
```

### 2. Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv_312
.\venv_312\Scripts\activate          # Windows
# source venv_312/bin/activate        # macOS / Linux

pip install -r requirements.txt

# Create and configure .env
copy .env.example .env
# Edit .env — see Environment Variables section below

# Start the backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

The database file is created automatically at `backend/bridgestone_it_agent.db` on first startup.

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000

npm run dev
```

- UI: `http://localhost:3000`

---

## Environment Variables

All variables are set in `backend/.env` for the backend and `frontend/.env.local` for the frontend.

### Backend

```env
# ── AI Providers ──────────────────────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key          # Optional; used as fallback

# ── ServiceNow ────────────────────────────────────────────────────────────────
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=api_user
SERVICENOW_PASSWORD=api_password
SERVICENOW_CLIENT_ID=oauth_client_id
SERVICENOW_CLIENT_SECRET=oauth_client_secret
SERVICENOW_USE_MOCK=false                         # true = disable live SN calls

# ── Authentication ────────────────────────────────────────────────────────────
JWT_SECRET_KEY=your_jwt_secret_min_32_chars
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=480

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=sqlite:///./bridgestone_it_agent.db
# DATABASE_URL=postgresql://user:password@localhost:5432/bridgestone_db

# ── Rate Limiting ─────────────────────────────────────────────────────────────
RATE_LIMIT_CHAT=30
RATE_LIMIT_CHAT_WINDOW=60
RATE_LIMIT_LOGIN=10
RATE_LIMIT_LOGIN_WINDOW=60

# ── Security ──────────────────────────────────────────────────────────────────
HSTS_ENABLED=false              # Set true in production (HTTPS only)
MAX_REQUEST_SIZE_KB=512

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### Frontend

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

---

## Docker Deployment

All Docker configuration lives in `infrastructure/`:

```
infrastructure/
├── compose/
│   ├── docker-compose.dev.yml
│   └── docker-compose.prod.yml
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── postgres.Dockerfile
├── env/
│   ├── dev.env
│   └── prod.env
├── monitoring/
│   └── docker-compose.monitoring.yml
└── nginx/
```

### Development Stack

```bash
cd infrastructure/compose
docker compose -f docker-compose.dev.yml up --build -d

# View logs
docker compose -f docker-compose.dev.yml logs -f

# Stop
docker compose -f docker-compose.dev.yml down
```

**Services started:**

| Service | Container | Port |
|---|---|---|
| PostgreSQL | `bridgestone-postgres-dev` | `5432` |
| Backend | `bridgestone-backend-dev` | `8000` |
| Frontend | `bridgestone-frontend-dev` | `3000` |

### Production Stack

```bash
cd infrastructure/compose
docker compose -f docker-compose.prod.yml up --build -d
```

All internal ports are locked down; only the NGINX reverse proxy is exposed:

- Frontend: `http://localhost/`
- API: `http://localhost/api/`

### Startup Order

```mermaid
graph LR
    PG[PostgreSQL] -->|healthy| BE[Backend]
    BE -->|healthy| FE[Frontend]
    FE --> NGINX[NGINX]
```

| Service | Health check command |
|---|---|
| PostgreSQL | `pg_isready -U postgres -d bridgestone_it_agent` |
| Backend | `GET http://localhost:8000/health` |
| Frontend | `GET http://localhost:3000/` |

---

## Monitoring Stack (Optional)

```bash
docker compose \
  -f docker-compose.prod.yml \
  -f ../monitoring/docker-compose.monitoring.yml \
  up -d
```

| Service | Port | Purpose |
|---|---|---|
| Prometheus | `9090` | Scrapes `GET /metrics` |
| Grafana | `3001` | Dashboards |

**Available Prometheus metric groups:**
- HTTP request counts, latencies, error rates
- Database query durations and failure counts
- LLM request counts, latencies, rate-limit events
- Security events: logins, failures, permission denials
- Business metrics: tickets created, resolved, SLA breaches

---

## Log Access

```bash
# Stream backend logs
docker logs bridgestone-backend-prod -f

# Last 100 lines
docker logs bridgestone-backend-prod --tail 100

# All services
docker compose -f docker-compose.prod.yml logs -f
```

Structured JSON log fields: `timestamp`, `level`, `request_id`, `correlation_id`, `session_id`, `user`, `role`, `endpoint`, `execution_time`, `status_code`.

---

## Database Backup

### PostgreSQL

```bash
# Create a backup
docker exec bridgestone-postgres-prod \
  pg_dump -U postgres bridgestone_it_agent > backup_$(Get-Date -Format yyyyMMdd).sql

# Restore from backup
docker exec -i bridgestone-postgres-prod \
  psql -U postgres bridgestone_it_agent < backup_20260101.sql
```

### SQLite (development)

```bash
copy backend\bridgestone_it_agent.db backup\bridgestone_it_agent_$(Get-Date -Format yyyyMMdd).db
```

---

## Production Readiness Checklist

### Environment

- [ ] `JWT_SECRET_KEY` set to a randomly generated 256-bit value
- [ ] `DATABASE_URL` points to production PostgreSQL
- [ ] Default user passwords changed (`employee`, `manager`, `admin`)
- [ ] `CORS_ORIGINS` restricted to production domain(s)
- [ ] `SERVICENOW_USE_MOCK=false` if connecting to live ServiceNow
- [ ] `GEMINI_API_KEY` set to a valid production API key
- [ ] `HSTS_ENABLED=true` if serving over HTTPS

### Infrastructure

- [ ] Backend port `8000` not exposed publicly
- [ ] Frontend port `3000` not exposed publicly
- [ ] NGINX configured for TLS
- [ ] Database backups scheduled
- [ ] Log aggregation configured

### Application

- [ ] `GET /health` returns `{"status": "healthy"}`
- [ ] `GET /system-status` returns all critical services healthy
- [ ] `GET /servicenow/validate` returns VALID for all configured fields

---

## Scaling

For higher-availability deployments:

1. **Backend:** Run multiple Uvicorn workers with Gunicorn:
   ```
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

2. **Database:** Switch `DATABASE_URL` to a managed PostgreSQL service.

3. **Rate Limiting:** Replace the in-process sliding-window limiter with Redis-backed implementation when running multiple backend instances.

4. **Load Balancing:** NGINX supports upstream load balancing across multiple backend instances.

---

## Related Documents

- [Architecture](./architecture.md) — Service structure and background jobs
- [Security](./Security.md) — Secrets management and default accounts
- [Configuration](./configuration.md) — All environment variables reference
