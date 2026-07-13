# Deployment Guide – Bridgestone IT Agent

> **Version:** 1.0.0 | **Last updated:** 2026-07-11

---

## 1. Prerequisites

| Requirement | Minimum version |
|-------------|----------------|
| Docker | 24.x |
| Docker Compose | 2.x (v2 syntax) |
| Node.js | 18.x (for local frontend dev) |
| Python | 3.12 (for local backend dev) |

---

## 2. Environment Configuration

All runtime configuration is managed through environment files in `infrastructure/env/`.

### Required Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string, e.g. `postgresql://postgres:password@postgres:5432/bridgestone_it_agent` |
| `SECRET_KEY` | JWT signing key (minimum 32 random bytes, hex-encoded) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `REDIS_URL` | Redis connection string, e.g. `redis://redis:6379/0` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins |

### ServiceNow Variables (optional – uses mock if absent)

| Variable | Description |
|----------|-------------|
| `SERVICENOW_INSTANCE` | ServiceNow instance subdomain |
| `SERVICENOW_USERNAME` | ServiceNow API username |
| `SERVICENOW_PASSWORD` | ServiceNow API password |
| `USE_MOCK_SERVICENOW` | Set to `true` to use mock data (default) |

### Frontend Variables

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL, e.g. `http://localhost:8000` |

---

## 3. Local Development Setup (without Docker)

### 3.1 Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your settings

# Start the backend server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
Interactive API docs: `http://localhost:8000/docs`

---

### 3.2 Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
copy .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:3000`.

---

## 4. Docker Deployment

### 4.1 Development Stack

The development stack includes hot-reloading and volume mounts for rapid iteration.

```bash
cd infrastructure/compose

# Start all services (postgres, redis, backend, frontend)
docker compose -f docker-compose.dev.yml up --build -d

# View logs
docker compose -f docker-compose.dev.yml logs -f

# Stop services
docker compose -f docker-compose.dev.yml down
```

**Services started:**

| Service | Container | Port |
|---------|-----------|------|
| PostgreSQL | `bridgestone-postgres-dev` | `5432` |
| Redis | `bridgestone-redis-dev` | `6379` |
| Backend | `bridgestone-backend-dev` | `8000` |
| Frontend | `bridgestone-frontend-dev` | `3000` |

---

### 4.2 Production Stack

The production stack builds immutable containers and routes traffic through NGINX.

```bash
cd infrastructure/compose

# Build and start all services
docker compose -f docker-compose.prod.yml up --build -d

# View logs
docker compose -f docker-compose.prod.yml logs -f backend

# Stop services
docker compose -f docker-compose.prod.yml down
```

**Access:**
- Application: `http://localhost/` (port 80 via NGINX)
- API: `http://localhost/api/`

---

## 5. Startup Order & Health Checks

Docker Compose enforces service startup order via `depends_on` with health conditions:

```mermaid
graph LR
    PG[PostgreSQL] -->|healthy| BE[Backend]
    Redis[Redis] -->|healthy| BE
    BE[Backend] -->|healthy| FE[Frontend]
    FE --> NGINX[NGINX]
```

**Health check commands:**

| Service | Health check |
|---------|-------------|
| PostgreSQL | `pg_isready -U postgres -d bridgestone_it_agent` |
| Redis | `redis-cli ping` |
| Backend | HTTP GET `http://localhost:8000/health` |
| Frontend | HTTP GET `http://localhost:3000/` |

---

## 6. Container Images

Each service has its own Dockerfile in `infrastructure/docker/`:

| Dockerfile | Service |
|------------|---------|
| `backend.Dockerfile` | FastAPI Python backend |
| `frontend.Dockerfile` | Next.js frontend (multi-stage build) |
| `postgres.Dockerfile` | PostgreSQL with seed data |
| `redis.Dockerfile` | Redis cache |

---

## 7. Monitoring Stack (Optional)

The `infrastructure/monitoring/` directory contains Prometheus and Grafana configuration.

To enable monitoring:

```bash
# Add to your docker-compose command
docker compose -f docker-compose.prod.yml -f monitoring/docker-compose.monitoring.yml up -d
```

| Service | Port | Purpose |
|---------|------|---------|
| Prometheus | `9090` | Metrics scraping |
| Grafana | `3001` | Metrics visualisation |

The backend exposes Prometheus metrics at `GET /metrics`.

**Available metric groups:**
- HTTP request counts, latencies, failures
- Database query durations, transaction counts, failure counts
- LLM API request counts, latencies, failure counts
- Security events: logins, failed logins, permission denials
- Active DB connections

---

## 8. Production Readiness Checklist

Before going live, verify the following:

### Environment
- [ ] `SECRET_KEY` set to a randomly generated 256-bit value
- [ ] `DATABASE_URL` points to production PostgreSQL
- [ ] Default user passwords changed (`employee`, `manager`, `admin`)
- [ ] `CORS_ORIGINS` restricted to production domain(s)
- [ ] `USE_MOCK_SERVICENOW=false` if connecting to live ServiceNow
- [ ] `GEMINI_API_KEY` set to a valid production API key

### Infrastructure
- [ ] Backend port `8000` not exposed publicly
- [ ] Frontend port `3000` not exposed publicly
- [ ] NGINX configured for TLS (HTTPS)
- [ ] Database backups scheduled
- [ ] Log aggregation configured (e.g., ELK, Azure Monitor)

### Application
- [ ] Run `python backend/verify_production_readiness.py` — all checks pass
- [ ] `GET /health` returns `{"status": "healthy"}`
- [ ] `GET /system-status` returns all adapters healthy or acceptable mock status

---

## 9. Log Access

```bash
# Stream backend logs
docker logs bridgestone-backend-prod -f

# Stream frontend logs
docker logs bridgestone-frontend-prod -f

# Stream all service logs
docker compose -f docker-compose.prod.yml logs -f

# View last 100 lines of backend logs
docker logs bridgestone-backend-prod --tail 100
```

The backend uses structured JSON logging. Each log entry includes:
- `timestamp`, `level`, `logger`
- `request_id`, `correlation_id`, `session_id`
- `user`, `role`, `endpoint`
- `execution_time`, `status_code`, `method`, `path`

---

## 10. Database Backup

### PostgreSQL (Docker)

```bash
# Create a backup
docker exec bridgestone-postgres-prod \
  pg_dump -U postgres bridgestone_it_agent > backup_$(date +%Y%m%d).sql

# Restore from backup
docker exec -i bridgestone-postgres-prod \
  psql -U postgres bridgestone_it_agent < backup_20260101.sql
```

### SQLite (development)

```bash
# Simple file copy
copy backend\bridgestone_it_agent.db backup\bridgestone_it_agent_$(date +%Y%m%d).db
```

---

## 11. Scaling

For high-availability production deployments:

1. **Backend:** Run multiple Uvicorn workers with Gunicorn:
   ```
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

2. **Database:** Use a managed PostgreSQL service (Azure Database for PostgreSQL, AWS RDS) with read replicas.

3. **Session storage:** Redis is already configured as a backend dependency; use a managed Redis service (Azure Cache for Redis, AWS ElastiCache) for horizontal scaling.

4. **Load balancing:** NGINX supports upstream load balancing across multiple backend instances.
