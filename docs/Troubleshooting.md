# Troubleshooting Guide – Bridgestone IT Agent

> **Version:** 1.0.0 | **Last updated:** 2026-07-11

---

## 1. Backend Startup Issues

### `database is locked` (SQLite)

**Symptom:** `sqlalchemy.exc.OperationalError: database is locked` in logs.

**Cause:** Multiple processes attempting concurrent writes to the same SQLite file. This occurs when multiple uvicorn workers or test processes start simultaneously.

**Fix:**
1. Kill all Python processes accessing the database:
   ```powershell
   Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like "*bridgestone-it-agent*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
   ```
2. Restart the backend:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

**Root cause:** SQLite uses WAL mode and file-level locking. For production, use PostgreSQL.

---

### `PendingRollbackError` (SQLAlchemy)

**Symptom:** `sqlalchemy.exc.PendingRollbackError: This Session's transaction has been rolled back due to a previous exception during flush`

**Cause:** A previous DB write failed (e.g., database locked), leaving the SQLAlchemy session in a rolled-back state. Subsequent queries on the same session fail.

**Fix:** The backend uses `try/finally` session management in `get_db_context()`. If this occurs mid-request, the session is automatically closed and recreated on the next request. No manual intervention required.

If it persists, restart the backend.

---

### `[WinError 10048] Only one usage of each socket address`

**Symptom:** `ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`

**Cause:** Another process is already listening on port 8000.

**Fix:**
```powershell
# Find and kill the process on port 8000
$proc = (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess
Stop-Process -Id $proc -Force
```

---

### Backend fails to connect to PostgreSQL

**Symptom:** Warning in logs: `Falling back to local SQLite database`

**Cause:** `DATABASE_URL` is not set or PostgreSQL is not running.

**Fix:**
1. Verify PostgreSQL is running
2. Check `DATABASE_URL` in your `.env` file
3. Test connectivity: `psql $DATABASE_URL -c "SELECT 1"`

If you intentionally want SQLite for development, this warning is expected and safe to ignore.

---

### `SECURITY WARNING: The default development JWT secret key is active`

**Symptom:** Warning logged at startup.

**Cause:** `SECRET_KEY` environment variable is not set.

**Fix for production:** Set `SECRET_KEY` to a securely generated value:
```bash
export SECRET_KEY=$(openssl rand -hex 32)
```

**Development:** This warning can be safely ignored in development environments.

---

### `No module named 'psycopg2'`

**Symptom:** Error in logs when connecting to PostgreSQL.

**Cause:** `psycopg2` (PostgreSQL driver) is not installed.

**Fix:**
```bash
pip install psycopg2-binary
```

---

## 2. Frontend Issues

### `Failed to fetch` / Network errors in browser console

**Symptom:** API calls fail with `Failed to fetch` or `ERR_CONNECTION_REFUSED`.

**Cause:** Backend server is not running or `NEXT_PUBLIC_API_URL` is misconfigured.

**Fix:**
1. Ensure the backend is running: `curl http://localhost:8000/health`
2. Check `NEXT_PUBLIC_API_URL` in `frontend/.env.local`
3. The frontend implements graceful backend unavailability detection — after 3 failed attempts, polling pauses automatically

---

### `401 Unauthorized` on all requests

**Symptom:** All API calls return `401`.

**Cause:** JWT access token has expired (tokens expire in 30 minutes).

**Fix:** The frontend should automatically refresh the token using the refresh token. If it does not:
1. Log out and log back in
2. Check the browser's localStorage for `access_token` and `refresh_token`

---

### Frontend shows blank page

**Symptom:** Next.js app loads but shows nothing.

**Fix:**
1. Check browser console for JavaScript errors
2. Verify `NEXT_PUBLIC_API_URL` is set and reachable
3. Run `npm run build` to check for compilation errors

---

## 3. Authentication Issues

### Login fails with `401`

**Possible causes:**
- Wrong username or password
- User account is deactivated (`is_active = False`)
- JWT `SECRET_KEY` changed (all existing tokens invalidated)

**Fix:**
1. Verify credentials in the `users` table
2. Check if `is_active` is `True`
3. If `SECRET_KEY` changed, all users must log in again

---

### `Token has expired`

**Symptom:** API returns `401` with `"Token has expired"`.

**Cause:** Access token lifetime (30 minutes) exceeded.

**Fix:** Use `POST /auth/refresh` with the refresh token to get a new access token. The frontend handles this automatically on 401 responses.

---

## 4. RBAC / Permission Issues

### `403 Forbidden – You do not have permission`

**Symptom:** Manager or Employee gets a 403 on an admin endpoint.

**Cause:** The user's role does not have the required permission.

**Fix:**
1. Check the user's role in the database: `SELECT username, role FROM users WHERE username='<username>'`
2. Review the permission matrix in [Security.md](Security.md)
3. If the role is wrong, update it: `UPDATE users SET role='MANAGER' WHERE username='<username>'`

---

### `ACCESS_DENIED` in AI chat

**Symptom:** Employee receives `⛔ ACCESS_DENIED – Your role EMPLOYEE does not have permission to perform Approve Privileged Action`.

**Cause:** This is expected behaviour. Employees cannot approve privileged actions (e.g., VPN access restoration). Only Managers and Admins can approve.

**Resolution:** The employee's manager must log in and approve the pending request.

---

## 5. Chat & AI Issues

### AI responds with generic answers

**Symptom:** AI does not provide troubleshooting steps for VPN/Outlook/Printer issues.

**Cause:**
1. `GEMINI_API_KEY` is not set — AI falls back to generic responses
2. Knowledge base articles not found for the category

**Fix:**
1. Set `GEMINI_API_KEY` in your environment
2. Check knowledge base: `ls knowledge_base/vpn/` — should contain JSON files

---

### Chat session gets stuck

**Symptom:** AI keeps asking the same question or doesn't progress.

**Fix:**
1. Type "restart" or "start over" to reset the conversation
2. Or start a new session (clear `session_id` from the request)

---

### Ticket not created after "create ticket" command

**Symptom:** User says "create ticket" but no ticket is created.

**Cause:** ServiceNow adapter failure (if `USE_MOCK_SERVICENOW=false` and ServiceNow is unreachable).

**Fix:**
1. Check backend logs for `ServiceNow` errors
2. Set `USE_MOCK_SERVICENOW=true` for testing
3. The AI will offer alternatives: retry, save as draft, or contact helpdesk directly

---

## 6. SLA & Scheduler Issues

### SLA jobs not running

**Symptom:** `GET /jobs` shows jobs are disabled or last_run_time is stale.

**Cause:**
- Scheduler disabled in testing mode (`TESTING=true`)
- APScheduler failed to start

**Fix:**
1. Check `GET /system-status` → `scheduler` section
2. Verify `TESTING` env var is not set in production
3. Check backend logs for `APScheduler` startup errors
4. Manually trigger: `POST /jobs/run/sla_monitor_job`

---

### Notifications not being sent

**Symptom:** SLA breached but no notifications appear.

**Cause:** Notification records are created in the database but the `notification_job` may not be running.

**Fix:**
1. Check `GET /jobs` — verify `notification_job` is enabled
2. Check `GET /notifications` — records should exist in the database
3. Verify the notification_job is triggered: `POST /jobs/run/notification_job`

---

## 7. Verification Test Failures

### Integration tests fail with `ConnectionRefusedError`

**Symptom:** `verify_*.py` test scripts fail with `urllib.error.URLError: <urlopen error [WinError 10061]>`

**Cause:** The test script tries to start a uvicorn server on port 8000, but the port is already occupied.

**Fix:**
```powershell
# Kill any process on port 8000
$proc = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($proc) { Stop-Process -Id $proc -Force }
```

Then re-run the test.

---

### `verify_troubleshooting_service.py` fails with `No such file or directory`

**Symptom:** `[Errno 2] No such file or directory: 'app\services\troubleshooting_service.py'`

**Cause:** The verification script is run from the wrong working directory.

**Fix:** Run verification scripts from the `backend/` directory:
```bash
cd backend
python verify_troubleshooting_service.py
```

Or use the orchestrated test runner:
```bash
python scratch/run_all_tests.py
```

---

## 8. Docker Issues

### Container fails to start: `bind: address already in use`

**Fix:**
```bash
# Find the conflicting process
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Kill it or change the Docker port mapping
```

---

### `pg_isready` health check fails

**Symptom:** PostgreSQL container shows as unhealthy.

**Fix:**
1. Check container logs: `docker logs bridgestone-postgres-dev`
2. Verify `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` environment variables are set

---

### Frontend container builds but shows wrong API URL

**Symptom:** Next.js app calls the wrong backend URL.

**Cause:** `NEXT_PUBLIC_API_URL` is baked in at build time in Next.js.

**Fix:** Rebuild the frontend container with the correct build arg:
```bash
docker compose build --build-arg NEXT_PUBLIC_API_URL=http://your-backend-url frontend
```

---

## 9. Performance Issues

### Slow API responses (> 5 seconds)

**Possible causes:**

| Cause | Diagnosis | Fix |
|-------|-----------|-----|
| Gemini API latency | Check `GET /system-status` → `gemini` latency | Not fixable — external API |
| Database query slow | Check `db_query_duration_seconds` metrics | Add indexes, optimise queries |
| SQLite under load | `database is locked` errors | Switch to PostgreSQL |
| No connection pooling | SQLite uses NullPool | Switch to PostgreSQL |

---

### High memory usage

**Cause:** SQLAlchemy session not closed properly, or conversation history growing unbounded.

**Fix:**
1. Verify `get_db_context()` properly closes sessions in `finally`
2. Conversation history is stored in `conversation_memory.py` — check memory growth
3. The `cleanup_job` removes stale sessions; ensure it is running

---

## 10. Collecting Debug Information

When reporting a bug, collect the following:

```bash
# Backend version and status
curl http://localhost:8000/health
curl http://localhost:8000/system-status -H "Authorization: Bearer <token>"

# Recent backend logs (last 200 lines)
docker logs bridgestone-backend-prod --tail 200

# Database tables
sqlite3 backend/bridgestone_it_agent.db ".tables"

# Environment (do NOT share actual secret values)
python -c "import os; [print(k) for k in os.environ if 'BRIDGESTONE' in k or 'DATABASE' in k or 'SECRET' in k]"
```
