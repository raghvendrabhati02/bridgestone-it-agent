# Bridgestone IT Agent — Configuration Guide

This guide details the configurations, system parameters, and environment settings required to customize and boot the Bridgestone IT Agent.

---

## 1. Environment Configurations

System parameters are loaded from `.env` files or system environment variables. The variables are split into three configuration environments:

* **Local Development (`dev.env`):** Configured with SQLite database fallbacks and debugging metrics.
* **Staging / QA (`qa.env`):** Implements immutable container builds and mock Gemini override modes for testing.
* **Production (`prod.env`):** Locks down external ports, enables strict PostgreSQL pool limits, and enforces SSL database connections.

### Configuration Properties

| Property | Environment Default | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://postgres:password@postgres:5432/bridgestone_it_agent` | Connection endpoint for database engine. SQLite fallback: `sqlite:///bridgestone_it_agent.db`. |
| `REDIS_URL` | `redis://redis:6379/0` | Connection endpoint for caching and locks. |
| `JWT_SECRET` | *Must be generated dynamically* | Cryptographic key used to sign session access and refresh tokens. |
| `GEMINI_API_KEY` | *Acquired from Google Cloud Console* | Google Generative AI integration key. |
| `SERVICENOW_URL` | `https://bridgestone-poc.service-now.com/` | Base URL of ServiceNow REST endpoints. |
| `SERVICENOW_USERNAME` | `api_user` | ServiceNow API access username. |
| `SERVICENOW_PASSWORD` | `api_password` | ServiceNow API access password. |

---

## 2. Production Database Connection Pooling

For PostgreSQL connections, the application tunes connection pooling parameters in `app/database/connection.py` to prevent database exhaustion under high concurrency loads:

* **`pool_size=20`:** Sets the maximum number of persistent connections to keep open in the pool.
* **`max_overflow=10`:** Allows spawning up to 10 additional connections during sudden concurrent request surges.
* **`pool_timeout=30`:** Limits block/wait time for acquiring an available connection from the pool to 30 seconds.
* **`pool_recycle=1800`:** Recycles active connections older than 30 minutes to clean stale client configurations.

### SQLite Fallback Performance Tuning

If PostgreSQL is unavailable, the application falls back to SQLite, applying critical performance parameters to prevent database locks during concurrent writes:
* **WAL Mode (Write-Ahead Logging):** Configured via `PRAGMA journal_mode=WAL` to allow simultaneous reads and writes.
* **NORMAL Synchronous:** Configured via `PRAGMA synchronous=NORMAL` to optimize transaction writes.
* **Timeout Lock:** Sets lock wait duration to `1.5` seconds (`connect_args={"timeout": 1.5}`) to prevent database locking issues.

---

## 3. Logging Thresholds & Audit Controls

Logs are managed dynamically via standard python logging configurations:

* **Application Logs:** Output using standard format `%(asctime)s [%(levelname)s] %(name)s: %(message)s` on `stdout`.
* **Trace Logs:** Agent paths, nodes visited, and decisions are persisted to the database (`agent_traces` table) for auditor inspection.
* **RBAC Audit Log:** Access approvals, denies, and updates are logged to the database (`rbac_audit_logs` table) with the operator's user metadata.
