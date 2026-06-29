# Bridgestone IT Agent — Troubleshooting Guide

This guide describes operational diagnostics, common failure modes, recovery playbooks, and mitigation scripts for the Bridgestone IT Support platform.

---

## 1. Database Lock Errors & SQLite Timeout

### Symptom:
Console logs print database errors:
`sqlalchemy.exc.OperationalError: database is locked` or `Central Exception Handler: Unhandled error: database is locked`.

### Root Cause:
* Concurrent writes occur while SQLite is in default DELETE journal mode, locking the database file.
* Connection timeouts are set too low, causing database write collisions.

### Recovery Playbook:
1. **Enable WAL Mode:** Confirm WAL mode is enabled in `app/database/connection.py`.
2. **Increase Timeout:** Set SQLite timeout parameter to at least `1.5` or `2.0` seconds in connection settings:
   `connect_args={"timeout": 2.0}`
3. **Migrate to PostgreSQL:** For production-grade concurrent loads, migrate to PostgreSQL where concurrency is managed by row locks.

---

## 2. PostgreSQL Connection Pool Exhaustion

### Symptom:
API endpoints fail with a TimeoutError:
`TimeoutError: QueuePool limit of size 20 overflow 10 reached, connection timed out, timeout 30`.

### Root Cause:
* Connections are opened but not properly closed (e.g. database sessions are leaked or not bound to context managers).
* Sudden concurrent traffic surges exceed pool capacity.

### Recovery Playbook:
1. **Verify Session Close:** Confirm all database endpoints wrap Session queries inside context managers or route through FastAPI's `Depends(get_db_context)`.
2. **Increase Pool Capacity:** Increase `pool_size` and `max_overflow` in `connection.py` or customize them via environment configuration:
   `pool_size=30`, `max_overflow=15`.

---

## 3. Gemini API Rate Limits (429 / Resource Exhausted)

### Symptom:
LLM operations fail with errors:
`429 Resource Exhausted` or fallback rules trigger on category detection.

### Root Cause:
* High volume of incoming user messages exhausts the Google Gemini API project quota limits.

### Recovery Playbook:
1. **Rule-Based Fallbacks:** The platform is built to automatically default to rule-based fallback routing (e.g. `detect_intent` fallback classifiers) if LLM calls fail, preventing backend crashes.
2. **Mocking Client for Offline Testing:** For testing or load validations, run scripts with `import mock_gemini` to intercept and mock model responses offline without exhausting live API keys.
3. **Upgrade Quota Limits:** Request an increase in Queries Per Minute (QPM) limits inside the Google Cloud Console project.

---

## 4. ServiceNow or Microsoft Graph Adapter Failure

### Symptom:
System fails to sync tickets or fetch user profiles:
`ServiceNowAdapter: Request failed...` or `MicrosoftGraphAdapter: Failed to synchronize...`.

### Recovery Playbook:
1. **Connectivity Check:** Run a ping test from the backend container to verify the target URL endpoint is reachable:
   `docker exec -it bridgestone-backend-prod ping servicenow.com`
2. **Verify Credentials:** Inspect `.env` settings to verify the API keys, integration passwords, and usernames are correct.
3. **Mock Adapter Mode:** If ServiceNow is offline in sandbox environments, the adapter defaults to returning structured mock data with serial numbers (`REQ000101` - `REQ000104`) to prevent service blockages.
