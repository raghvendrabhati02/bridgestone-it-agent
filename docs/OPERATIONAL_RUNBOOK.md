# Operational Runbook & Production Hardening Guide

## 1. Security Architecture & Hardening

### Authentication & Token Management
- **JWT Signing**: Access tokens use `HS256` HMAC signing with strict `type: "access"` and `type: "refresh"` claim validation.
- **Expiration Policies**: Access tokens expire in 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`), refresh tokens expire in 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`).
- **Secret Keys**: `SECRET_KEY` and `JWT_SECRET` are environment-driven. The system warns on default dev keys and fails fast on startup in production.

### Input Validation & Sanitization
- **XSS & Injection Protection**: User input fields are validated via Pydantic schemas and escaped using `sanitize_input()`.
- **Request Body Size Limits**: `RequestSizeLimitMiddleware` rejects payloads exceeding `MAX_REQUEST_SIZE_KB` (default 512 KB) with HTTP 413.

### Security Headers
`SecurityHeadersMiddleware` automatically injects security headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` (or `SAMEORIGIN`)
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=()`

---

## 2. Rate Limiting Configuration

In-process sliding-window rate limiting (`rate_limiter.py`) applies tier limits:

| Role | Default Limit | Environment Variable |
|---|---|---|
| **Anonymous** | 20 requests / min | `RATE_LIMIT_ANONYMOUS` |
| **Employee** | 60 requests / min | `RATE_LIMIT_EMPLOYEE` |
| **Manager** | 120 requests / min | `RATE_LIMIT_MANAGER` |
| **Admin** | 300 requests / min | `RATE_LIMIT_ADMIN` |

When exceeded, the API returns `HTTP 429 Too Many Requests` with a `Retry-After` header.

---

## 3. Database Backup & Recovery Procedure

### Backup Command
Execute the backup utility script:
```bash
# Full backup (database + environment configuration)
python backend/scripts/backup_recovery.py backup --output-dir ./backups

# Config-only backup
python backend/scripts/backup_recovery.py backup-config --output-dir ./backups
```

### Recovery Command
Restore a database backup:
```bash
python backend/scripts/backup_recovery.py restore --file ./backups/sqlite_backup_YYYYMMDD_HHMMSS.db
```

---

## 4. Incident Response & Troubleshooting Runbook

### Health Check Diagnostic Commands
```bash
# Deep component health check
curl -f http://localhost:8000/health

# Readiness probe
curl -f http://localhost:8000/ready

# Liveness probe
curl -f http://localhost:8000/live

# Metrics export
curl -f http://localhost:8000/metrics
```

### Log Inspection
Structured JSON logs include `correlation_id`, `request_id`, `user`, `endpoint`, and `execution_time`:
```bash
# Filter logs by Correlation ID
docker compose logs backend | grep "corr-12345678"

# Filter logs by ERROR level
docker compose logs backend | grep '"level":"ERROR"'
```
