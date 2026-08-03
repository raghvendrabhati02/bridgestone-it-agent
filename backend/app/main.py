import logging
import os
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.conversation_service import handle_chat_turn
from app.services.ticket_service import (
    get_all_tickets,
    create_ticket
)
from app.services.notification_service import get_notifications
from app.services.rag_service import get_document_for_category
from app.integrations.servicenow.servicenow_models import IncidentCreateRequest
from app.adapters.servicenow_adapter import ServiceNowAdapter
from app.adapters.microsoft_graph_adapter import MicrosoftGraphAdapter
from app.services.action_service import get_all_actions
from app.services.audit_service import (
    get_all_audit_logs,
    get_all_actions_history,
    get_all_approvals_history,
    get_all_agent_traces
)

# Authentication & Security imports
from app.core.security import get_current_user, RoleChecker, get_db_context
from app.api.auth import router as auth_router
from app.api.analytics import router as analytics_router
from app.database.models.user import User


# Initialize ServiceNow Adapter for API routing
snow_adapter = ServiceNowAdapter()

# Initialize Microsoft Graph Adapter for API routing
graph_adapter = MicrosoftGraphAdapter()

# Initialize Active Directory / Entra ID Adapter for API routing
from app.adapters.active_directory_adapter import ActiveDirectoryAdapter
ad_adapter = ActiveDirectoryAdapter()

# Set up logging format and logger instance
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("it-agent-backend")

from contextlib import asynccontextmanager

# ── Phase 5: Readiness flag ───────────────────────────────────────────────────
# Toggled True once startup is complete, False when shutdown begins.
# Used by GET /ready for lightweight Kubernetes/load-balancer probing.
_app_ready: bool = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app_ready

    # ── Sprint 9: Validate application environment configuration ───────────────
    from app.core.config_validator import validate_environment_config
    is_valid_cfg, cfg_errs = validate_environment_config()
    if not is_valid_cfg and os.getenv("ENVIRONMENT", "").lower() in ("production", "prod"):
        raise RuntimeError(f"Startup configuration validation failed: {cfg_errs}")

    # ── Phase 3: Activate structured JSON logging on startup ─────────────────
    import logging as _logging
    _json_logging_enabled = os.getenv("JSON_LOGGING", "true").lower() in ("1", "true", "yes")
    if _json_logging_enabled:
        from app.core.json_logger import setup_json_logging
        setup_json_logging(_logging.INFO)


    # Phase 7 Startup Validation
    if os.getenv("SERVICENOW_ENABLED", "false").lower() == "true":
        logger.info("ServiceNow Integration: Validating production configuration during startup...")
        from app.services.servicenow_service import get_servicenow_service
        sn_service = get_servicenow_service()
        is_valid, err_msg = sn_service.validate_configuration()
        if not is_valid:
            logger.error("❌ ServiceNow Configuration Check Failed: %s", err_msg)
            print(f"[X] ServiceNow Configuration Check Failed: {err_msg}")
        else:
            health = sn_service.health_check()
            if health.get("authenticated"):
                logger.info("✅ ServiceNow Connected (%s)", health.get("instance"))
                print(f"[OK] ServiceNow Connected ({health.get('instance')})")
            else:
                logger.error("❌ ServiceNow Authentication Failed: %s", health.get("message"))
                print(f"[X] ServiceNow Authentication Failed: {health.get('message')})")
    else:
        logger.info("ServiceNow Integration is disabled (SERVICENOW_ENABLED=false)")

    # Initialize Mock ITSM database tables and seed data
    try:
        from app.mock_itsm.database import init_mock_itsm_db
        init_mock_itsm_db()
        logger.info("✓ Mock ITSM Platform initialized successfully.")
    except Exception as mock_init_err:
        logger.warning("WARNING: Mock ITSM initialization exception: %s", mock_init_err)

    # ── Phase 5: Mark application as ready ───────────────────────────────────
    _app_ready = True
    logger.info("Application startup complete. Readiness probe: READY.")

    yield

    # ── Phase 5: Mark application as not-ready during graceful shutdown ───────
    _app_ready = False
    logger.info("Application shutdown initiated. Readiness probe: NOT READY.")

app = FastAPI(
    title="Bridgestone IT Agent",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health/servicenow")
def servicenow_health_check_endpoint():
    """
    Phase 8: ServiceNow Health Check Endpoint.
    Returns JSON status, authenticated, instance, version, and latency_ms.
    """
    from app.services.servicenow_service import get_servicenow_service
    sn_service = get_servicenow_service()
    return sn_service.health_check()


@app.get("/metadata/health")
def servicenow_metadata_health_check_endpoint():
    """
    Phase 6.2: ServiceNow Metadata Cache & Health Endpoint.
    Returns JSON status, source, last_refresh, cache_age_seconds, and record counts.
    """
    from app.services.servicenow_metadata_cache import ServiceNowMetadataCache
    cache = ServiceNowMetadataCache.get_instance()
    return cache.get_stats()


@app.get("/ready")
def readiness_probe():
    """
    Phase 5: Kubernetes / load-balancer readiness probe.

    Returns 200 once the application has completed startup and is ready to
    accept traffic.  Returns 503 during startup or graceful shutdown.

    This endpoint is intentionally lightweight — it does NOT query the database,
    Redis, or any external API.  Use GET /health for a deep health check.
    """
    from fastapi.responses import JSONResponse
    if _app_ready:
        return JSONResponse(
            status_code=200,
            content={"status": "ready", "message": "Application is ready to accept traffic."},
        )
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "message": "Application is still starting up or shutting down."},
    )


@app.get("/live")
def liveness_probe():
    """
    Sprint 8: Kubernetes / load-balancer liveness probe.

    Returns 200 OK while the application process is active.
    Used by container orchestrators / load balancers to detect process crashes.
    """
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=200,
        content={
            "status": "alive",
            "service": "bridgestone-it-agent",
            "message": "Application process is active."
        },
    )



# Mount static files for screenshots
from fastapi.staticfiles import StaticFiles
IMAGES_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "images"))
os.makedirs(IMAGES_DIR_PATH, exist_ok=True)
app.mount("/images", StaticFiles(directory=IMAGES_DIR_PATH), name="images")

# Enable CORS Middleware to allow requests from the Next.js frontend (e.g., http://localhost:3000)
cors_origins_env = os.getenv("CORS_ORIGINS")
if cors_origins_env:
    origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()]
else:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]


# ── Phase 4: Security Middleware ─────────────────────────────────────────────
from app.core.security_middleware import SecurityHeadersMiddleware, RequestSizeLimitMiddleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "X-Request-ID", "X-Session-ID", "Accept"],
    # ── Phase 5: Expose correlation/request IDs so browser clients can read them ──
    expose_headers=["X-Correlation-ID", "X-Request-ID"],
)

import time

SESSION_CORRELATION_CACHE = {}

def get_correlation_id_for_session(session_id: str) -> str:
    if not session_id:
        return ""
    if session_id in SESSION_CORRELATION_CACHE:
        return SESSION_CORRELATION_CACHE[session_id]
    db = None
    try:
        from app.database.connection import SessionLocal
        db = SessionLocal()
        from app.database.models.agent_trace import AgentTrace
        trace = db.query(AgentTrace).filter(AgentTrace.session_id == session_id).filter(AgentTrace.correlation_id != None).first()
        if trace:
            SESSION_CORRELATION_CACHE[session_id] = trace.correlation_id
            return trace.correlation_id
        from app.database.models.audit_log import AuditLog
        log = db.query(AuditLog).filter(AuditLog.session_id == session_id).filter(AuditLog.correlation_id != None).first()
        if log:
            SESSION_CORRELATION_CACHE[session_id] = log.correlation_id
            return log.correlation_id
    except Exception:
        pass
    finally:
        if db:
            db.close()
    return ""


def save_session_correlation(session_id: str, correlation_id: str):
    if session_id and correlation_id:
        SESSION_CORRELATION_CACHE[session_id] = correlation_id

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    from app.core.metrics import (
        HTTP_REQUESTS_TOTAL, HTTP_FAILURES_TOTAL, HTTP_REQUEST_DURATION_SECONDS,
        REQUEST_TIMESTAMPS, ERROR_TIMESTAMPS, API_LATENCIES
    )
    from app.core.logging_context import (
        clear_logging_context, request_id_ctx, correlation_id_ctx,
        session_id_ctx, user_ctx, role_ctx, endpoint_ctx, error_stack_ctx
    )
    import uuid
    import time
    import traceback
    
    method = request.method
    path = request.url.path
    
    # Exclude probe/diagnostic endpoints from polluting metrics
    if path in ("/metrics", "/system-status", "/health", "/ready", "/live", "/health/servicenow"):
        return await call_next(request)
        
    clear_logging_context()
    
    # 1. Generate request_id
    req_id = f"req-{uuid.uuid4().hex[:8]}"
    request_id_ctx.set(req_id)
    endpoint_ctx.set(path)
    
    # 2. Extract session_id from query, header, or body
    session_id = request.query_params.get("session_id") or request.headers.get("x-session-id")
    if not session_id and request.headers.get("content-type") == "application/json":
        try:
            body_bytes = await request.body()
            async def receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            request._receive = receive
            import json
            body_data = json.loads(body_bytes)
            session_id = body_data.get("session_id")
        except Exception:
            pass
            
    if session_id:
        session_id_ctx.set(session_id)
        
    # 3. Extract correlation_id
    corr_id = request.headers.get("x-correlation-id") or request.query_params.get("correlation_id")
    if not corr_id:
        corr_id = get_correlation_id_for_session(session_id)
        if not corr_id:
            corr_id = f"corr-{uuid.uuid4().hex[:8]}"
            if session_id:
                save_session_correlation(session_id, corr_id)
    correlation_id_ctx.set(corr_id)
    
    # 4. Extract user/role from JWT token
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        db_sess = None
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            username = payload.get("sub")
            if username:
                user_ctx.set(username)
                from app.database.connection import SessionLocal
                db_sess = SessionLocal()
                from app.database.models.user import User
                user = db_sess.query(User).filter(User.username == username).first()
                if user:
                    role_ctx.set(user.role)
        except Exception:
            pass
        finally:
            if db_sess:
                db_sess.close()
            
    # Track request timestamp
    now = time.time()
    REQUEST_TIMESTAMPS.append(now)
    cutoff = now - 60.0
    while REQUEST_TIMESTAMPS and REQUEST_TIMESTAMPS[0] < cutoff:
        REQUEST_TIMESTAMPS.pop(0)

    try:
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path).inc()
    except Exception:
        pass

    # ── Phase 5: Import async_trace_span for root HTTP span ────────────────────
    from app.core.tracing import async_trace_span
    start_time = time.time()
    status_code = 500
    # ── Phase 5: Root HTTP span — wraps entire request lifecycle ──────────────
    async with async_trace_span(
        name="http_request",
        attributes={
            "provider": "none",
            "method": method,
            "path": path,
            "correlation_id": corr_id,
        },
    ):
        try:
            response = await call_next(request)
            status_code = response.status_code
            # ── Phase 5: Propagate Correlation ID back to the client ──────────
            response.headers["X-Correlation-ID"] = corr_id
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as e:
            tb = traceback.format_exc()
            error_stack_ctx.set(tb)

            ERROR_TIMESTAMPS.append(now)
            while ERROR_TIMESTAMPS and ERROR_TIMESTAMPS[0] < cutoff:
                ERROR_TIMESTAMPS.pop(0)

            raise e
        finally:
            duration = time.time() - start_time

            # Save latency
            API_LATENCIES.append({
                "method": method,
                "path": path,
                "duration": duration,
                "timestamp": now
            })
            if len(API_LATENCIES) > 1000:
                API_LATENCIES.pop(0)

            if status_code >= 400:
                ERROR_TIMESTAMPS.append(now)
                while ERROR_TIMESTAMPS and ERROR_TIMESTAMPS[0] < cutoff:
                    ERROR_TIMESTAMPS.pop(0)

            try:
                HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
                if status_code >= 400:
                    HTTP_FAILURES_TOTAL.labels(method=method, path=path, status_code=str(status_code)).inc()
            except Exception:
                pass

            logger.info(
                "Request processing complete.",
                extra={
                    "execution_time": duration,
                    "status_code": status_code,
                    "method": method,
                    "path": path
                }
            )
            clear_logging_context()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    from app.core.logging_context import error_stack_ctx
    tb = traceback.format_exc()
    error_stack_ctx.set(tb)
    
    logger.error("Central Exception Handler: Unhandled error: %s", exc, exc_info=True)
    
    err_msg = "An unexpected error occurred. Please try again later."
    status_code = 500
    
    exc_name = type(exc).__name__
    if exc_name == "HTTPException":
        status_code = exc.status_code
        err_msg = exc.detail
    elif "timeout" in str(exc).lower() or "deadline" in str(exc).lower():
        err_msg = "The request timed out. Please check your connection and try again."
        status_code = 504
    elif "locked" in str(exc).lower() or "busy" in str(exc).lower():
        err_msg = "The database is currently busy. Please retry shortly."
        status_code = 503
    elif "permission" in str(exc).lower() or "unauthorized" in str(exc).lower() or "forbidden" in str(exc).lower():
        err_msg = "You are not authorized to perform this operation."
        status_code = 403
        
    from app.core.logging_context import correlation_id_ctx
    corr_id = correlation_id_ctx.get() or ""
    
    response_body = {"detail": err_msg, "error_code": exc_name}
    if corr_id:
        response_body["correlation_id"] = corr_id

    headers = {"X-Correlation-ID": corr_id} if corr_id else {}
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content=response_body,
        headers=headers
    )


@app.get("/metrics")
def get_metrics(request: Request, db: Session = Depends(get_db_context)):
    """
    Prometheus metrics endpoint.

    Access control is configurable via METRICS_PROTECTION env var:
      network  (default) — no auth required; restrict at network/proxy level
      auth               — requires ADMIN role Bearer token
    """
    protection = os.getenv("METRICS_PROTECTION", "network").lower()
    if protection == "auth":
        try:
            from app.core.security import get_current_user as _get_user, RoleChecker, get_db_context as _get_db
            admin_checker = RoleChecker(["ADMIN"])
            auth_header = request.headers.get("authorization", "")
            if not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required for metrics access",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            from app.core.security import decode_token
            payload = decode_token(auth_header.split(" ", 1)[1])
            username = payload.get("sub")
            if not username:
                raise HTTPException(status_code=401, detail="Invalid token")
            user = db.query(User).filter(User.username == username).first()
            if not user or user.role != "ADMIN":
                raise HTTPException(status_code=403, detail="ADMIN role required for metrics access")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/system-status")
def system_status(
    db: Session = Depends(get_db_context),
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
):
    logger.info("FastAPI Endpoint GET '/system-status': Status checked")
    
    now = time.time()
    cutoff = now - 60.0
    from app.core.metrics import REQUEST_TIMESTAMPS, ERROR_TIMESTAMPS, API_LATENCIES, AI_LATENCIES
    
    while REQUEST_TIMESTAMPS and REQUEST_TIMESTAMPS[0] < cutoff:
        REQUEST_TIMESTAMPS.pop(0)
    while ERROR_TIMESTAMPS and ERROR_TIMESTAMPS[0] < cutoff:
        ERROR_TIMESTAMPS.pop(0)
        
    rpm = len(REQUEST_TIMESTAMPS)
    errors = len(ERROR_TIMESTAMPS)
    error_rate = (errors / max(1, rpm)) * 100.0
    
    slowest = {}
    for item in API_LATENCIES:
        key = (item["method"], item["path"])
        if key not in slowest or item["duration"] > slowest[key]:
            slowest[key] = item["duration"]
    slowest_apis = [
        {"method": k[0], "path": k[1], "duration": round(v, 4)}
        for k, v in sorted(slowest.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    avg_ai_latency = sum(AI_LATENCIES) / max(1, len(AI_LATENCIES)) if AI_LATENCIES else 0.0
    
    from app.database.models.action_history import ActionHistory
    total_actions = 0
    success_actions = 0
    try:
        total_actions = db.query(ActionHistory).count()
        success_actions = db.query(ActionHistory).filter(ActionHistory.status == "SUCCESS").count()
    except Exception:
        pass
    tool_success_rate = (success_actions / max(1, total_actions)) * 100.0 if total_actions > 0 else 100.0
    
    from app.database.models.agent_trace import AgentTrace
    import datetime
    active_sessions = 0
    try:
        day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        active_sessions = db.query(AgentTrace.session_id).filter(AgentTrace.created_at >= day_ago).distinct().count()
    except Exception:
        pass
        
    from app.database.models.notification import Notification
    notification_backlog = 0
    try:
        notification_backlog = db.query(Notification).filter(Notification.status.in_(["PENDING", "QUEUED"])).count()
    except Exception:
        pass
        
    from app.jobs.scheduler import scheduler_instance
    scheduler_state = "STOPPED"
    if scheduler_instance and scheduler_instance.running:
        scheduler_state = "RUNNING"
        
    h = health(db)
    
    return {
        "status": h["status"],
        "database": h["database"],
        "redis": h["redis"],
        "gemini": h["gemini"],
        "adapters": h["adapters"],
        "scheduler_state": scheduler_state,
        "rpm": rpm,
        "error_rate": round(error_rate, 2),
        "slowest_apis": slowest_apis,
        "average_ai_latency": round(avg_ai_latency, 4),
        "tool_success_rate": round(tool_success_rate, 2),
        "active_sessions": active_sessions,
        "notification_backlog": notification_backlog,
        "metrics_summary": {
            "rpm": rpm,
            "error_rate": round(error_rate, 2),
            "average_ai_latency": round(avg_ai_latency, 4),
            "tool_success_rate": round(tool_success_rate, 2),
            "active_sessions": active_sessions,
            "notification_backlog": notification_backlog
        }
    }

# Include Auth & Mock ITSM Routers
from app.mock_itsm.api import router as mock_itsm_router
app.include_router(auth_router)
app.include_router(analytics_router)
app.include_router(mock_itsm_router)


# ── Sprint 10: AI Admin & Analytics API Endpoints ─────────────────────────────

@app.get("/api/admin/ai/evaluation")
def get_ai_evaluation_endpoint(
    db: Session = Depends(get_db_context),
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    from app.services.ai_evaluation_service import get_ai_evaluation_metrics
    return get_ai_evaluation_metrics(db)

@app.get("/api/admin/ai/prompts")
def get_prompts_endpoint(current_user: User = Depends(RoleChecker(["ADMIN"]))):
    from app.services.prompt_management_service import get_all_prompts
    return get_all_prompts()

@app.post("/api/admin/ai/prompts/{prompt_key}")
def update_prompt_endpoint(
    prompt_key: str,
    payload: dict = Body(...),
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    from app.services.prompt_management_service import update_prompt
    content = payload.get("content", "")
    return update_prompt(prompt_key, content, updated_by=current_user.username)

@app.get("/api/admin/ai/prompts/{prompt_key}/history")
def get_prompt_history_endpoint(
    prompt_key: str,
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    from app.services.prompt_management_service import get_prompt_history
    return get_prompt_history(prompt_key)

@app.post("/api/admin/ai/prompts/{prompt_key}/restore/{version}")
def restore_prompt_version_endpoint(
    prompt_key: str,
    version: str,
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    from app.services.prompt_management_service import restore_prompt_version
    res = restore_prompt_version(prompt_key, version, restored_by=current_user.username)
    if not res:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return res

@app.get("/api/admin/ai/settings")
def get_ai_settings_endpoint(current_user: User = Depends(RoleChecker(["ADMIN"]))):
    from app.services.ai_settings_service import get_ai_settings
    return get_ai_settings()

@app.put("/api/admin/ai/settings")
def update_ai_settings_endpoint(
    payload: dict = Body(...),
    current_user: User = Depends(RoleChecker(["ADMIN"]))
):
    from app.services.ai_settings_service import update_ai_settings
    return update_ai_settings(payload, updated_by=current_user.username)

@app.get("/api/admin/ai/model-health")
def get_model_health_endpoint(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    from app.services.ai_settings_service import get_model_health_stats
    return get_model_health_stats()

@app.post("/api/chat/feedback")
def submit_chat_feedback_endpoint(
    payload: dict = Body(...),
    current_user: User = Depends(get_current_user)
):
    from app.services.ai_feedback_service import submit_feedback
    session_id = payload.get("session_id", "default")
    rating = payload.get("rating", "helpful")
    comment = payload.get("comment", "")
    ticket_id = payload.get("ticket_id", "")
    return submit_feedback(session_id, rating, user_id=current_user.username, comment=comment, ticket_id=ticket_id)

@app.get("/api/admin/ai/feedback")
def get_ai_feedback_summary_endpoint(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    from app.services.ai_feedback_service import get_feedback_summary
    return get_feedback_summary()

@app.get("/api/admin/ai/conversations")
def search_conversations_endpoint(
    q: str = None,
    status: str = None,
    db: Session = Depends(get_db_context),
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    from app.services.ai_feedback_service import search_conversations
    return search_conversations(q=q, status_filter=status, db=db)

@app.post("/api/admin/ai/rebuild-index")
def rebuild_knowledge_index_endpoint(current_user: User = Depends(RoleChecker(["ADMIN"]))):
    import app.services.knowledge_service as ks
    count = ks.load_articles()
    return {"message": "Knowledge base index rebuilt successfully", "indexed_articles": count}

@app.post("/api/admin/ai/clear-cache")
def clear_ai_cache_endpoint(current_user: User = Depends(RoleChecker(["ADMIN"]))):
    try:
        from app.services.servicenow_metadata_cache import ServiceNowMetadataCache
        ServiceNowMetadataCache.get_instance().clear()
    except Exception:
        pass
    return {"message": "AI and metadata caches cleared successfully"}



class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User message (max 4000 chars)")
    session_id: str | None = Field(default=None, max_length=128)

class TicketCreateRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    issue_description: str = Field(..., min_length=1, max_length=2000)

@app.get("/")
def home():
    logger.info("FastAPI Endpoint GET '/': Heartbeat requested")
    return {
        "message": "Bridgestone IT Agent Running"
    }

@app.get("/health")
def health(db: Session = Depends(get_db_context)):
    logger.info("FastAPI Endpoint GET '/health': Health status checked")
    
    # 1. Database connection check
    db_status = "unhealthy"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error("Health Check: DB connection failed: %s", e)

    # 2. Redis connection check
    redis_status = "unhealthy"
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, socket_timeout=1)
        r.ping()
        redis_status = "healthy"
        try:
            from app.core.metrics import REDIS_AVAILABILITY
            REDIS_AVAILABILITY.set(1)
        except Exception:
            pass
    except Exception as e:
        logger.error("Health Check: Redis connection failed: %s", e)
        redis_status = "unhealthy"
        try:
            from app.core.metrics import REDIS_AVAILABILITY
            REDIS_AVAILABILITY.set(0)
        except Exception:
            pass

    # 3. AI Provider check
    gemini_status = "unhealthy"
    try:
        from app.services.ai_provider import get_ai_provider, google_genai
        sdk_loaded = google_genai is not None
        api_key_present = bool(os.getenv("GEMINI_API_KEY"))
        
        # Check if provider is initialized in the singleton
        from app.services.ai_provider import _active_provider
        provider_initialized = _active_provider is not None
        
        # Get verification state
        verification_state = "NOT_STARTED"
        if provider_initialized:
            verification_state = getattr(_active_provider, "_verify_status", "NOT_STARTED")
        
        provider = get_ai_provider()
        if provider.is_ready():
            gemini_status = f"healthy (SDK Loaded: {sdk_loaded}, Key Present: {api_key_present}, Initialized: {provider_initialized}, Verification: {verification_state})"
        else:
            gemini_status = f"unconfigured (SDK Loaded: {sdk_loaded}, Key Present: {api_key_present}, Initialized: {provider_initialized}, Verification: {verification_state})"
    except Exception as e:
        logger.error("Health Check: AI provider configuration failed: %s", e)
        gemini_status = f"unhealthy ({e})"


    # 4. Enterprise Adapters Check
    adapters_status = {}
    try:
        from app.adapters.servicenow_adapter import ServiceNowAdapter
        from app.adapters.microsoft_graph_adapter import MicrosoftGraphAdapter
        from app.adapters.active_directory_adapter import ActiveDirectoryAdapter
        from app.adapters.vpn_adapter import VPNAdapter

        # ServiceNow
        try:
            sn = ServiceNowAdapter()
            if not getattr(sn.client, "is_mock", True):
                res = sn.client.check_connectivity()
                adapters_status["ServiceNow"] = {
                    "status": "healthy" if res.get("status") == "healthy" else "unhealthy",
                    "latency": res.get("latency", 0.0),
                    "details": res.get("details", "")
                }
            else:
                adapters_status["ServiceNow"] = {
                    "status": "healthy",
                    "latency": 0.0,
                    "details": "Mock Mode active."
                }
        except Exception as e:
            adapters_status["ServiceNow"] = {
                "status": "unhealthy",
                "latency": 0.0,
                "details": f"unhealthy: {e}"
            }

        # Microsoft Graph
        try:
            mg = MicrosoftGraphAdapter()
            if not getattr(mg.client, "is_mock", True):
                res = mg.client.check_connectivity()
                adapters_status["Microsoft Graph"] = {
                    "status": "healthy" if res.get("status") == "healthy" else "unhealthy",
                    "latency": res.get("latency", 0.0),
                    "details": res.get("details", ""),
                    "token_expiry": res.get("token_expiry", 0)
                }
            else:
                adapters_status["Microsoft Graph"] = {
                    "status": "healthy",
                    "latency": 0.0,
                    "details": "Mock Mode active.",
                    "token_expiry": 9999999999
                }
        except Exception as e:
            adapters_status["Microsoft Graph"] = {
                "status": "unhealthy",
                "latency": 0.0,
                "details": f"unhealthy: {e}",
                "token_expiry": 0
            }

        # Active Directory
        try:
            if not getattr(ad_adapter.client, "is_mock", True):
                res = ad_adapter.client.check_connectivity()
                adapters_status["Active Directory"] = {
                    "status": "healthy" if res.get("status") == "healthy" else "unhealthy",
                    "latency": res.get("latency", 0.0),
                    "details": res.get("details", ""),
                    "token_expiry": res.get("token_expiry", 0)
                }
            else:
                adapters_status["Active Directory"] = {
                    "status": "healthy",
                    "latency": 0.0,
                    "details": "Mock Mode active.",
                    "token_expiry": 9999999999
                }
        except Exception as e:
            adapters_status["Active Directory"] = {
                "status": "unhealthy",
                "latency": 0.0,
                "details": f"unhealthy: {e}",
                "token_expiry": 0
            }

        # VPN Gateway
        try:
            vpn = VPNAdapter()
            adapters_status["VPN"] = "healthy" if vpn.health_check() else "unhealthy"
        except Exception as e:
            adapters_status["VPN"] = f"unhealthy: {e}"
    except Exception as e:
        logger.error("Health Check: Adapters check failed: %s", e)
        adapters_status["error"] = str(e)

    # 5. Scheduler Check
    scheduler_status = {
        "running": False,
        "jobs": []
    }
    try:
        from app.jobs.scheduler import scheduler_instance
        from app.database.models.scheduled_job import ScheduledJob, JobExecutionHistory
        
        if scheduler_instance:
            scheduler_status["running"] = bool(scheduler_instance.running)
            
        jobs = db.query(ScheduledJob).all()
        for j in jobs:
            live_job = scheduler_instance.get_job(j.job_name) if scheduler_instance else None
            next_run = live_job.next_run_time.replace(tzinfo=None).isoformat() + "Z" if (live_job and live_job.next_run_time) else (j.next_run_time.isoformat() + "Z" if j.next_run_time else None)
            
            # Check last execution status in history
            last_exec = db.query(JobExecutionHistory).filter(JobExecutionHistory.job_name == j.job_name).order_by(JobExecutionHistory.started_at.desc()).first()
            last_status = last_exec.status if last_exec else "unknown"
            
            scheduler_status["jobs"].append({
                "job_name": j.job_name,
                "is_enabled": j.is_enabled,
                "last_run_time": j.last_run_time.isoformat() + "Z" if j.last_run_time else None,
                "next_run_time": next_run,
                "last_execution_status": last_status,
                "is_active": live_job is not None
            })
    except Exception as e:
        logger.error("Health Check: Scheduler check failed: %s", e)
        scheduler_status["error"] = str(e)

    # 6. Overall status determination
    def is_adapter_healthy(s):
        if isinstance(s, dict):
            return s.get("status") == "healthy"
        return s == "healthy"

    is_healthy = (
        db_status == "healthy" and
        gemini_status == "healthy" and
        all(is_adapter_healthy(s) for s in adapters_status.values())
    )

    if is_healthy:
        overall_status = "healthy"
    elif db_status == "unhealthy":
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "database": db_status,
        "redis": redis_status,
        "gemini": gemini_status,
        "adapters": adapters_status,
        "scheduler": scheduler_status
    }


@app.post("/chat")
def chat(request: ChatRequest, raw_request: Request, current_user: User = Depends(get_current_user)):
    import time
    from app.core.rate_limiter import check_rate_limit
    from app.services.prompt_guard import scan_message, PromptInjectionError
    from app.core.logging_context import correlation_id_ctx

    # Phase 4: Rate limiting
    check_rate_limit(raw_request, "chat")

    # Phase 4: Prompt injection guard
    safe_message = request.message
    try:
        safe_message = scan_message(request.message, correlation_id=correlation_id_ctx.get() or "")
    except PromptInjectionError as pie:
        logger.warning(
            "POST /chat: Prompt injection blocked for user=%s: %s",
            current_user.username, pie,
        )
        raise HTTPException(status_code=400, detail=str(pie))

    t0 = time.time()
    logger.info(">>> TRACE START: FastAPI Endpoint POST '/chat' | User: %s | Session ID: %s", current_user.username, request.session_id)
    try:
        response_payload = handle_chat_turn(request.session_id, safe_message, username=current_user.username, user_role=current_user.role)
        elapsed = (time.time() - t0) * 1000
        logger.info("<<< TRACE END: FastAPI Endpoint POST '/chat' | Elapsed: %.2f ms", elapsed)
        return response_payload
    except HTTPException:
        raise
    except Exception as exc:
        elapsed = (time.time() - t0) * 1000
        logger.error("!!! TRACE ERROR: FastAPI Endpoint POST '/chat' | Elapsed: %.2f ms | Error: %s", elapsed, exc, exc_info=True)
        raise


@app.get("/tickets")
@app.get("/my-tickets")
def list_tickets(
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    assigned_team: str | None = None,
    assigned_engineer: str | None = None,
    created_by: str | None = None,
    sla_state: str | None = None,
    sla_breached: bool | None = None,
    search: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/tickets': Fetching tickets with filters for user %s", current_user.username)
    from app.database.models.ticket import Ticket
    import datetime

    query = db.query(Ticket)

    # RBAC constraint: EMPLOYEE can only see their own tickets
    if current_user.role not in ("ADMIN", "MANAGER"):
        query = query.filter(Ticket.created_by == current_user.username)

    # Apply filters
    if status:
        query = query.filter(Ticket.status == status.upper().strip())
    if priority:
        query = query.filter(Ticket.priority == priority.upper().strip())
    if category:
        query = query.filter(Ticket.category == category.upper().strip())
    if assigned_team:
        query = query.filter(Ticket.assigned_team == assigned_team.strip())
    if assigned_engineer:
        query = query.filter(Ticket.assigned_engineer == assigned_engineer.strip())
    if created_by:
        query = query.filter(Ticket.created_by == created_by.strip())
    if sla_state:
        query = query.filter(Ticket.sla_state == sla_state.upper().strip())
    if sla_breached is not None:
        query = query.filter(Ticket.sla_breached == sla_breached)

    if search:
        query = query.filter(
            Ticket.ticket_id.like(f"%{search}%") |
            Ticket.description.like(f"%{search}%") |
            Ticket.issue_description.like(f"%{search}%")
        )

    if created_after:
        try:
            dt_after = datetime.datetime.fromisoformat(created_after.replace("Z", ""))
            query = query.filter(Ticket.created_at >= dt_after)
        except Exception:
            pass
    if created_before:
        try:
            dt_before = datetime.datetime.fromisoformat(created_before.replace("Z", ""))
            query = query.filter(Ticket.created_at <= dt_before)
        except Exception:
            pass
            
    if updated_after:
        try:
            dt_up_after = datetime.datetime.fromisoformat(updated_after.replace("Z", ""))
            query = query.filter(
                (Ticket.created_at >= dt_up_after) |
                (Ticket.resolved_at >= dt_up_after) |
                (Ticket.closed_at >= dt_up_after)
            )
        except Exception:
            pass
    if updated_before:
        try:
            dt_up_before = datetime.datetime.fromisoformat(updated_before.replace("Z", ""))
            query = query.filter(
                (Ticket.created_at <= dt_up_before) |
                (Ticket.resolved_at <= dt_up_before) |
                (Ticket.closed_at <= dt_up_before)
            )
        except Exception:
            pass

    tickets_list = query.order_by(Ticket.created_at.desc()).all()

    # Map to dictionary output
    results = []
    for t in tickets_list:
        results.append({
            "ticket_id": t.ticket_id,
            "category": t.category,
            "description": t.description,
            "issue_description": t.issue_description,
            "assigned_team": t.assigned_team,
            "assigned_engineer": t.assigned_engineer,
            "priority": t.priority,
            "sla_hours": t.sla_hours,
            "status": t.status,
            "servicenow_id": t.servicenow_id,
            "created_by": t.created_by,
            "created_at": t.created_at.isoformat() + "Z",
            "updated_at": t.updated_at.isoformat() + "Z" if t.updated_at else t.created_at.isoformat() + "Z",
            "resolved_at": t.resolved_at.isoformat() + "Z" if t.resolved_at else None,
            "closed_at": t.closed_at.isoformat() + "Z" if t.closed_at else None,
            "sla_state": t.sla_state or "HEALTHY",
            "sla_breached": t.sla_breached or False,
            "sla_breached_at": t.sla_breached_at.isoformat() + "Z" if t.sla_breached_at else None,
            # ITSM Workflow fields
            "request_type": t.request_type,
            "manager": t.manager,
            "approval_status": t.approval_status,
            "assignment_group": t.assignment_group or t.assigned_team,
            "approved_by": getattr(t, "approved_by", None) or t.manager or ("manager" if t.approval_status == "APPROVED" else None),
            "approved_at": t.approved_at.isoformat() + "Z" if getattr(t, "approved_at", None) else (t.updated_at.isoformat() + "Z" if (t.approval_status == "APPROVED" and t.updated_at) else None),
            "approval_notes": getattr(t, "approval_notes", None) or ("Approved via Manager Portal." if t.approval_status == "APPROVED" else None),
            "software_requested": t.category if t.category in ["Software", "SOFTWARE_INSTALLATION", "SAP", "ADOBE", "CITRIX", "POWERBI"] else (
                "SAP GUI" if "sap" in (t.description or "").lower() else
                "Adobe Acrobat" if "adobe" in (t.description or "").lower() else
                "Microsoft Visio" if "visio" in (t.description or "").lower() else
                t.category
            ),
            "laps_active": getattr(t, "laps_active", False) or False,
            "laps_password": getattr(t, "laps_password", None),
            "laps_expiration": t.laps_expiration.isoformat() + "Z" if getattr(t, "laps_expiration", None) else None,
            "temp_admin_credentials": {
                "username": ".\\Administrator",
                "password": getattr(t, "laps_password", "Temp@4821#"),
                "status": "EXPIRED" if (getattr(t, "laps_expiration", None) and datetime.datetime.utcnow() > t.laps_expiration) else ("ACTIVE" if getattr(t, "laps_active", False) else "PENDING"),
                "valid_for_minutes": 15,
                "expires_at": t.laps_expiration.isoformat() + "Z" if getattr(t, "laps_expiration", None) else None,
                "source": "Mock Enterprise Integration"
            } if getattr(t, "laps_active", False) or t.status == "ACCESS_GRANTED" else None
        })
    return results

@app.post("/ticket")
def make_ticket(
    request: TicketCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint POST '/ticket': Creating manual ticket for category=%s, user=%s", request.category, current_user.username)
    res = create_ticket(request.category, request.issue_description, created_by=current_user.username, db=db)
    from app.services.notification_service import NotificationService
    NotificationService.notify_ticket_created(res, user_id=current_user.username, db=db)
    return res


class TicketActionRequest(BaseModel):
    action: str
    team: str | None = None
    priority: str | None = None
    note: str | None = None
    engineer: str | None = None


@app.post("/tickets/{ticket_id}/action")
def run_ticket_action(
    ticket_id: str,
    request: TicketActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint POST '/tickets/%s/action': Action=%s, user=%s", ticket_id, request.action, current_user.username)
    from app.database.models.ticket import Ticket
    from app.database.models.audit_log import AuditLog
    from app.database.models.rbac_audit_log import RbacAuditLog
    from app.services.rbac_audit_service import log_rbac_event
    from app.services.notification_service import create_notification
    from app.services.sla_service import calculate_sla
    import datetime

    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")

    old_status = ticket.status
    old_priority = ticket.priority
    old_team = ticket.assigned_team

    action = request.action.lower().strip()
    
    # ── Role-based access control gates ──────────────────────────────────────
    is_creator = (ticket.created_by == current_user.username)
    
    if action == "add_note":
        if current_user.role not in ("ADMIN", "MANAGER"):
            raise HTTPException(status_code=403, detail="Employees are not authorized to post or view internal work notes.")
    elif action in ("approve", "reject"):
        if current_user.role not in ("ADMIN", "MANAGER"):
            raise HTTPException(status_code=403, detail="Only Managers and Admins can approve or reject actions.")
    elif action in ("assign", "reassign", "transfer_team", "assign_team", "accept"):
        if current_user.role not in ("ADMIN", "MANAGER"):
            raise HTTPException(status_code=403, detail="Only Managers and Admins can assign or accept tickets.")
    elif action in ("manager_approve", "manager_reject"):
        if current_user.role not in ("MANAGER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only Managers can approve or reject service requests.")
    elif action == "reject_request":
        if current_user.role not in ("ADMIN", "MANAGER"):
            raise HTTPException(status_code=403, detail="Only Admins and Managers can reject requests.")
    elif action in ("start_work", "put_on_hold", "request_more_information", "change_priority", "resolve", "fulfill", "escalate", "pending", "admin_approve"):
        if current_user.role != "ADMIN":
            raise HTTPException(status_code=403, detail="Only Admin users can execute this ticket lifecycle action.")
    elif action in ("close", "confirm_resolution"):
        if current_user.role != "ADMIN" and not is_creator:
            raise HTTPException(status_code=403, detail="Only Admins or the ticket requester can close or confirm resolution.")
    elif action == "reopen":
        if current_user.role != "ADMIN" and not is_creator:
            raise HTTPException(status_code=403, detail="Only Admins or the ticket requester can reopen this ticket.")
    else:
        raise HTTPException(status_code=400, detail=f"Action '{request.action}' not recognized.")

    # ── Action Logic ────────────────────────────────────────────────────────
    
    if action == "add_note":
        if not request.note:
            raise HTTPException(status_code=400, detail="Note content is required for action 'add_note'.")
        from app.services.workflow_service import WorkflowService
        WorkflowService.add_comment(
            db=db,
            ticket_id=ticket_id,
            author=current_user.username,
            text=request.note,
            is_internal=True,
            role=current_user.role
        )
        db.commit()
        return {"message": "Internal note added successfully."}

    elif action in ("approve", "reject"):
        # Find session_id from AuditLog or RbacAuditLog
        audit_record = db.query(AuditLog).filter(AuditLog.ticket_id == ticket_id).first()
        session_id = audit_record.session_id if audit_record else None
        if not session_id:
            rbac_record = db.query(RbacAuditLog).filter(RbacAuditLog.ticket_id == ticket_id).first()
            if rbac_record and rbac_record.details:
                try:
                    import json
                    details_dict = json.loads(rbac_record.details)
                    session_id = details_dict.get("session_id")
                except Exception:
                    pass
        
        if not session_id:
            raise HTTPException(status_code=400, detail="No active session found to approve/reject.")
            
        status_str = "APPROVED" if action == "approve" else "REJECTED"
        from app.services.approval_service import update_approval
        update_approval(session_id, status_str)
        
        # Log to timeline
        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="APPROVAL_DECIDED",
            actor=current_user.username,
            action=action,
            description=f"Action approval {status_str.lower()} by {current_user.username}."
        )
        db.commit()
        return {"message": f"Action approval {status_str.lower()} successfully."}

    # ── ITSM: manager_approve ────────────────────────────────────────────────
    if action == "manager_approve":
        if ticket.request_type not in ("SERVICE_REQUEST", "PRIVILEGED_ACTION"):
            raise HTTPException(status_code=400, detail="Only SERVICE_REQUEST or PRIVILEGED_ACTION tickets require manager approval.")
        ticket.approval_status = "APPROVED"
        ticket.status = "APPROVED"
        db.commit()

        # Log Admin approval requested
        try:
            from app.database.models.session import SessionModel
            from app.core.logging_context import session_id_ctx
            from app.services.observability_service import log_event
            session_record = db.query(SessionModel).filter(SessionModel.active_ticket == ticket_id).first()
            if session_record:
                session_id_ctx.set(session_record.session_id)
                log_event(
                    "Admin approval requested",
                    db=db,
                    category=ticket.category,
                    ticket_id=ticket_id
                )
        except Exception as _obs_err:
            logger.warning("Failed to log admin approval requested: %s", _obs_err)

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="MANAGER_APPROVED",
            actor=current_user.username,
            action="manager_approve",
            description=f"Request approved by manager {current_user.username}. Forwarded to admin queue."
        )
        from app.services.notification_service import NotificationService
        NotificationService.notify_approval(
            ticket=ticket,
            approval_type=ticket.request_type or "SERVICE_REQUEST",
            status="APPROVED",
            approver=current_user.username,
            requester=ticket.created_by,
            db=db
        )
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="APPROVED",
            details={"action": "manager_approve", "note": request.note or ""}
        )
        db.commit()
        return {"message": "Request approved. Ticket moved to admin queue.", "status": "APPROVED", "approval_status": "APPROVED"}

    # ── ITSM: manager_reject ─────────────────────────────────────────────────
    elif action == "manager_reject":
        if ticket.request_type not in ("SERVICE_REQUEST", "PRIVILEGED_ACTION"):
            raise HTTPException(status_code=400, detail="Only SERVICE_REQUEST or PRIVILEGED_ACTION tickets can be rejected by manager.")
        ticket.approval_status = "REJECTED"
        ticket.status = "REJECTED"
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="MANAGER_REJECTED",
            actor=current_user.username,
            action="manager_reject",
            description=f"Request rejected by manager {current_user.username}. Reason: {request.note or 'No reason provided.'}"
        )
        from app.services.notification_service import NotificationService
        NotificationService.notify_approval(
            ticket=ticket,
            approval_type=ticket.request_type or "SERVICE_REQUEST",
            status="REJECTED",
            approver=current_user.username,
            requester=ticket.created_by,
            db=db
        )
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="REJECTED",
            details={"action": "manager_reject", "note": request.note or ""}
        )
        db.commit()
        return {"message": "Request rejected.", "status": "REJECTED", "approval_status": "REJECTED"}

    # ── ITSM: accept (admin accepts into queue) ──────────────────────────────
    elif action == "accept":
        ticket.status = "ASSIGNED"
        if ticket.approval_status not in ("APPROVED", "NOT_REQUIRED"):
            ticket.approval_status = "APPROVED"
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_ACCEPTED",
            actor=current_user.username,
            action="accept",
            description=f"Ticket accepted by admin {current_user.username} and moved to assigned queue."
        )
        from app.services.notification_service import create_notification as _notif
        _notif(ticket_id=ticket_id, recipient=ticket.created_by or "Employee",
               message=f"Your ticket {ticket_id} has been accepted and assigned to the IT team.")
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="ASSIGNED",
            details={"action": "accept", "note": request.note or ""}
        )
        db.commit()
        return {"message": "Ticket accepted and assigned.", "status": "ASSIGNED"}

    # ── ITSM: reject_request (admin hard-rejects) ────────────────────────────
    elif action == "reject_request":
        ticket.status = "REJECTED"
        ticket.approval_status = "REJECTED"
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="REQUEST_REJECTED",
            actor=current_user.username,
            action="reject_request",
            description=f"Request rejected by {current_user.role} {current_user.username}. Reason: {request.note or 'No reason provided.'}"
        )
        from app.services.notification_service import create_notification as _notif
        _notif(ticket_id=ticket_id, recipient=ticket.created_by or "Employee",
               message=f"Your request {ticket_id} has been rejected. Reason: {request.note or 'No reason provided.'}")
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="REJECTED",
            details={"action": "reject_request", "note": request.note or ""}
        )
        db.commit()
        return {"message": "Request rejected.", "status": "REJECTED"}

    # ── ITSM: resolve ────────────────────────────────────────────────────────
    elif action == "resolve":
        ticket.status = "RESOLVED"
        ticket.resolved_at = datetime.datetime.utcnow()
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_RESOLVED",
            actor=current_user.username,
            action="resolve",
            description=f"Ticket resolved by {current_user.username}. Resolution: {request.note or 'Issue resolved.'}"
        )
        from app.services.notification_service import NotificationService
        NotificationService.notify_resolution(ticket=ticket, resolved_by=current_user.username, db=db)
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="RESOLVED",
            details={"action": "resolve", "note": request.note or ""}
        )
        db.commit()
        return {"message": "Ticket resolved successfully.", "status": "RESOLVED"}

    # ── ITSM: close ──────────────────────────────────────────────────────────
    elif action == "close":
        ticket.status = "CLOSED"
        ticket.closed_at = datetime.datetime.utcnow()
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_CLOSED",
            actor=current_user.username,
            action="close",
            description=f"Ticket closed by {current_user.username}."
        )
        from app.services.notification_service import NotificationService
        NotificationService.notify_status_change(ticket=ticket, new_status="CLOSED", actor=current_user.username, db=db)
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="CLOSED",
            details={"action": "close", "note": request.note or ""}
        )
        db.commit()
        return {"message": "Ticket closed successfully.", "status": "CLOSED"}

    # ── ITSM: reopen ─────────────────────────────────────────────────────────
    elif action == "reopen":
        ticket.status = "IN_PROGRESS"
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_REOPENED",
            actor=current_user.username,
            action="reopen",
            description=f"Ticket reopened by {current_user.username}."
        )
        from app.services.notification_service import NotificationService
        NotificationService.notify_status_change(ticket=ticket, new_status="IN_PROGRESS", actor=current_user.username, db=db)
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="IN_PROGRESS",
            details={"action": "reopen", "note": request.note or ""}
        )
        db.commit()
        return {"message": "Ticket reopened.", "status": "IN_PROGRESS"}

    # ── ITSM: assign / reassign ──────────────────────────────────────────────
    elif action in ("assign", "reassign"):
        if getattr(request, "team", None):
            ticket.assigned_team = request.team
            ticket.assignment_group = request.team
        if getattr(request, "engineer", None):
            ticket.assigned_engineer = request.engineer
        ticket.status = "ASSIGNED"
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_ASSIGNED",
            actor=current_user.username,
            action=action,
            description=f"Ticket reassigned to team '{ticket.assigned_team}' / engineer '{ticket.assigned_engineer}' by {current_user.username}."
        )
        from app.services.notification_service import NotificationService
        NotificationService.notify_assignment(ticket=ticket, db=db)
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="ASSIGNED",
            details={"action": action, "team": ticket.assigned_team, "engineer": ticket.assigned_engineer}
        )
        db.commit()
        return {"message": "Ticket assigned successfully.", "status": "ASSIGNED"}

    # ── ITSM: start_work ─────────────────────────────────────────────────────
    elif action == "start_work":
        ticket.status = "IN_PROGRESS"
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="WORK_STARTED",
            actor=current_user.username,
            action="start_work",
            description=f"Work started on ticket by {current_user.username}."
        )
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="IN_PROGRESS",
            details={"action": "start_work"}
        )
        db.commit()
        return {"message": "Ticket work started.", "status": "IN_PROGRESS"}

    # ── ITSM: put_on_hold / pending ──────────────────────────────────────────
    elif action in ("put_on_hold", "pending"):
        ticket.status = "WAITING"
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_ON_HOLD",
            actor=current_user.username,
            action=action,
            description=f"Ticket placed on hold by {current_user.username}. Reason: {request.note or 'Awaiting customer response.'}"
        )
        log_rbac_event(
            user=current_user.username, role=current_user.role,
            action="update_ticket_lifecycle", ticket_id=ticket_id,
            old_state=old_status, new_state="WAITING",
            details={"action": action, "note": request.note or ""}
        )
        db.commit()
        return {"message": "Ticket placed on hold.", "status": "WAITING"}


# ── Sprint 5 Admin Endpoints ─────────────────────────────────────────────────

@app.get("/api/itsm/users")
def get_itsm_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Returns system users for Admin Portal Users view."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only Administrators can view users.")
    
    users = db.query(User).order_by(User.username.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() + "Z" if u.created_at else None
        }
        for u in users
    ]

@app.get("/api/itsm/assignment-groups")
def get_itsm_assignment_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Returns assignment groups and assigned workload metrics."""
    if current_user.role not in ("ADMIN", "MANAGER"):
        raise HTTPException(status_code=403, detail="Only Managers and Admins can view assignment groups.")
    
    groups = [
        {"name": "Helpdesk", "manager": "mgr_sarah", "engineers": ["Emily Watson (Helpdesk L2)", "John Helpdesk", "Sarah L1"]},
        {"name": "Network", "manager": "mgr_sarah", "engineers": ["Alex Net", "Dave Router"]},
        {"name": "Security", "manager": "admin_alex", "engineers": ["Security Officer", "Elena Sec"]},
        {"name": "Hardware", "manager": "mgr_sarah", "engineers": ["Hardware Tech", "Marcus Repair"]},
        {"name": "Database", "manager": "admin_alex", "engineers": ["DBA Lead", "Sql Master"]},
        {"name": "Access Management", "manager": "admin_alex", "engineers": ["IAM Admin", "Access Specialist"]},
        {"name": "Cloud Infrastructure", "manager": "admin_alex", "engineers": ["Cloud Ops", "Aws DevOps"]}
    ]
    
    from app.database.models.ticket import Ticket
    open_tickets = db.query(Ticket).filter(Ticket.status.notin_(["RESOLVED", "CLOSED", "REJECTED"])).all()
    group_counts = {}
    for t in open_tickets:
        grp = t.assignment_group or t.assigned_team or "Helpdesk"
        group_counts[grp] = group_counts.get(grp, 0) + 1

    for g in groups:
        g["open_tickets_count"] = group_counts.get(g["name"], 0)
        g["engineer_count"] = len(g["engineers"])

    return {"assignment_groups": groups}

@app.delete("/tickets/{ticket_id}")
def delete_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Allows Admin to delete a ticket."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only Administrators can delete tickets.")
    
    from app.database.models.ticket import Ticket
    from app.services.rbac_audit_service import log_rbac_event

    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")
    
    log_rbac_event(
        user=current_user.username,
        role=current_user.role,
        action="delete_ticket",
        ticket_id=ticket_id,
        old_state=ticket.status,
        new_state="DELETED",
        details={"deleted_by": current_user.username}
    )
    
    db.delete(ticket)
    db.commit()
    logger.info("Admin %s deleted ticket %s", current_user.username, ticket_id)
    return {"message": f"Ticket '{ticket_id}' has been permanently deleted.", "ticket_id": ticket_id}

@app.post("/tickets/{ticket_id}/update")
def update_ticket_details(
    ticket_id: str,
    updates: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Allows Admin to update ticket fields."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only Administrators can update full ticket details.")
    
    from app.database.models.ticket import Ticket
    from app.services.rbac_audit_service import log_rbac_event
    import datetime

    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")

    old_state = ticket.status
    if "category" in updates and updates["category"]:
        ticket.category = str(updates["category"])
    if "priority" in updates and updates["priority"]:
        ticket.priority = str(updates["priority"]).upper()
    if "status" in updates and updates["status"]:
        ticket.status = str(updates["status"]).upper()
    if "assigned_team" in updates and updates["assigned_team"]:
        ticket.assigned_team = str(updates["assigned_team"])
        ticket.assignment_group = str(updates["assigned_team"])
    if "assigned_engineer" in updates and updates["assigned_engineer"]:
        ticket.assigned_engineer = str(updates["assigned_engineer"])
    if "issue_description" in updates and updates["issue_description"]:
        ticket.issue_description = str(updates["issue_description"])
    
    ticket.updated_at = datetime.datetime.utcnow()
    db.commit()

    log_rbac_event(
        user=current_user.username,
        role=current_user.role,
        action="update_ticket_details",
        ticket_id=ticket_id,
        old_state=old_state,
        new_state=ticket.status,
        details=updates
    )
    db.commit()
    logger.info("Admin %s updated ticket %s: %s", current_user.username, ticket_id, updates)
    return {"message": "Ticket updated successfully", "ticket_id": ticket_id}

    # Otherwise we are updating fields
    new_status = old_status
    new_priority = old_priority
    new_team = old_team

    if action in ("assign", "reassign", "transfer_team", "assign_team"):
        new_team = request.team or ticket.assigned_team or "Helpdesk"
        new_engineer = request.engineer or ticket.assigned_engineer or "Emily Watson (Helpdesk L2)"
        
        from app.services.workflow_service import WorkflowService
        WorkflowService.assign_ticket(
            db=db,
            ticket_id=ticket_id,
            new_engineer=new_engineer,
            assigned_by=current_user.username,
            reason=request.note,
            new_group=new_team
        )
        new_status = "ASSIGNED"
        ticket.status = new_status
        db.commit()
        
        # Notify
        create_notification(
            ticket_id=ticket_id,
            recipient=new_team,
            message=f"Ticket {ticket_id} has been assigned to the {new_team} team."
        )
        create_notification(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Your ticket {ticket_id} has been assigned to the {new_team} team."
        )
        # Log Audit
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": request.action, "assigned_team": new_team, "assigned_engineer": new_engineer, "note": request.note or ""}
        )

    elif action == "change_priority":
        if not request.priority:
            raise HTTPException(status_code=400, detail="Priority level is required.")
        new_priority = request.priority.upper().strip()
        if new_priority not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            raise HTTPException(status_code=400, detail=f"Invalid priority level '{request.priority}'.")
        new_sla_hours = calculate_sla(new_priority)
        ticket.priority = new_priority
        ticket.sla_hours = new_sla_hours
        db.commit()

        # Log timeline event
        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="PRIORITY_CHANGED",
            actor=current_user.username,
            action="change priority",
            description=f"Priority changed to {new_priority}."
        )

        # Log Audit
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="change_priority",
            ticket_id=ticket_id,
            old_state=old_priority,
            new_state=new_priority,
            details={"action": "change_priority", "new_sla_hours": new_sla_hours, "note": request.note or ""}
        )

    elif action == "start_work":
        new_status = "IN_PROGRESS"
        ticket.status = new_status
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="WORK_STARTED",
            actor=current_user.username,
            action="start work",
            description=f"Work started on ticket by {current_user.username}."
        )

        create_notification(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Work has started on ticket {ticket_id}."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": "start_work", "note": request.note or ""}
        )

    elif action == "put_on_hold":
        new_status = "WAITING"
        ticket.status = new_status
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_ON_HOLD",
            actor=current_user.username,
            action="put on hold",
            description=f"Ticket put on hold by {current_user.username}."
        )

        create_notification(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Ticket {ticket_id} has been placed on hold."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": "put_on_hold", "note": request.note or ""}
        )

    elif action == "pending":
        new_status = "PENDING"
        ticket.status = new_status
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_PENDING",
            actor=current_user.username,
            action="pending",
            description=f"Ticket set to Pending by {current_user.username}."
        )

        create_notification(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Ticket {ticket_id} status updated to PENDING."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": "pending", "note": request.note or ""}
        )

    elif action in ("request_more_information", "request_information"):
        new_status = "WAITING_FOR_USER"
        ticket.status = new_status
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="INFORMATION_REQUESTED",
            actor=current_user.username,
            action="request information",
            description=f"Additional information requested by {current_user.username}."
        )

        create_notification(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Update request: Ticket {ticket_id} is awaiting input from you."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": "request_more_information", "note": request.note or ""}
        )

    elif action == "escalate":
        prio_flow = {"LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "CRITICAL", "CRITICAL": "CRITICAL"}
        new_priority = prio_flow.get(old_priority, "MEDIUM")
        new_sla_hours = calculate_sla(new_priority)
        ticket.priority = new_priority
        ticket.sla_hours = new_sla_hours
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_ESCALATED",
            actor=current_user.username,
            action="escalate",
            description=f"Ticket priority escalated to {new_priority}."
        )

        create_notification(
            ticket_id=ticket_id,
            recipient="Manager",
            message=f"Ticket {ticket_id} has been escalated to {new_priority} priority."
        )
        create_notification(
            ticket_id=ticket_id,
            recipient="Admin",
            message=f"Ticket {ticket_id} has been escalated to {new_priority} priority."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="escalate_ticket",
            ticket_id=ticket_id,
            old_state=old_priority,
            new_state=new_priority,
            details={"action": "escalate", "note": request.note or ""}
        )

    elif action == "resolve":
        is_sr = (ticket.request_type == "SERVICE_REQUEST")
        new_status = "FULFILLED" if is_sr else "RESOLVED"
        ticket.status = new_status
        ticket.resolved_at = datetime.datetime.utcnow()
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_FULFILLED" if is_sr else "TICKET_RESOLVED",
            actor=current_user.username,
            action="resolve",
            description=f"Ticket fulfilled by {current_user.username}." if is_sr else f"Ticket resolved by {current_user.username}."
        )

        from app.services.notification_service import NotificationService
        NotificationService.notify_resolution(ticket, db=db)
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": "resolve", "note": request.note or ""}
        )

    elif action == "fulfill":
        new_status = "FULFILLED"
        ticket.status = new_status
        ticket.resolved_at = datetime.datetime.utcnow()
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_FULFILLED",
            actor=current_user.username,
            action="fulfill",
            description=f"Ticket fulfilled by {current_user.username}."
        )

        create_notification(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Ticket {ticket_id} has been marked as FULFILLED."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": "fulfill", "note": request.note or ""}
        )

    elif action in ("close", "confirm_resolution"):
        new_status = "CLOSED"
        ticket.status = new_status
        ticket.closed_at = datetime.datetime.utcnow()
        db.commit()

        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_CLOSED",
            actor=current_user.username,
            action="close",
            description=f"Ticket closed by {current_user.username}."
        )

        create_notification(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Ticket {ticket_id} has been CLOSED."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": "close", "note": request.note or ""}
        )

    elif action == "reopen":
        from app.services.workflow_service import WorkflowService
        WorkflowService.reopen_ticket(
            db=db,
            ticket_id=ticket_id,
            reopened_by=current_user.username,
            reason=request.note or "Ticket reopened via administration control."
        )
        new_status = "ASSIGNED" if ticket.assigned_team else "OPEN"
        ticket.status = new_status
        db.commit()

        recipient = ticket.assigned_team or (ticket.created_by or "Employee")
        create_notification(
            ticket_id=ticket_id,
            recipient=recipient,
            message=f"Ticket {ticket_id} has been re-opened."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": "reopen", "note": request.note or ""}
        )

    elif action == "admin_approve":
        new_status = "TEMP_ADMIN_GRANTED"
        ticket.status = new_status

        # Generate simulated temporary Microsoft LAPS password
        # Format: BS-XXXX-XXXX-XX (alphanumeric, 14 chars after prefix)
        import random, string, secrets
        chars = string.ascii_letters + string.digits
        segments = [
            "".join(secrets.choice(chars) for _ in range(4)),
            "".join(secrets.choice(chars) for _ in range(4)),
            "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(2)),
        ]
        laps_pwd = f"BS-{'-'.join(segments)}"

        # Retrieve the manager who previously approved (for the audit trail)
        manager_name = ticket.manager or "manager"
        admin_name = current_user.username
        audit_ts = int(datetime.datetime.utcnow().timestamp())

        ticket.laps_password = laps_pwd
        ticket.laps_expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
        ticket.laps_active = True
        # Embed approver names in audit ID for display in UI
        ticket.laps_audit_id = f"LAPS-{ticket_id}-{audit_ts}"
        # Store approved-by metadata on the manager field for LAPS panel display
        # (manager already set when ticket was created; admin name stored in audit)
        db.commit()

        # Log LAPS password generated
        try:
            from app.database.models.session import SessionModel
            from app.core.logging_context import session_id_ctx
            from app.services.observability_service import log_event
            session_record = db.query(SessionModel).filter(SessionModel.active_ticket == ticket_id).first()
            if session_record:
                session_id_ctx.set(session_record.session_id)
                log_event(
                    "LAPS password generated",
                    db=db,
                    category=ticket.category,
                    ticket_id=ticket_id
                )
        except Exception as _obs_err:
            logger.warning("Failed to log laps password generated: %s", _obs_err)

        # Non-critical audit trail — wrapped to prevent any transient database write issues from blocking the response
        try:
            from app.services.timeline_service import TimelineService
            TimelineService.log_event(
                db=db,
                ticket_id=ticket_id,
                event_type="LAPS_GRANTED",
                actor=admin_name,
                action="admin_approve",
                description=(
                    f"Temporary administrator privileges granted by {admin_name} (Admin). "
                    f"Previously approved by {manager_name} (Manager). "
                    f"Audit ID: {ticket.laps_audit_id}. Expires in 15 minutes."
                )
            )
            create_notification(
                ticket_id=ticket_id,
                recipient=ticket.created_by or "Employee",
                message=(
                    f"✅ Temporary administrator privileges have been granted for ticket {ticket_id}. "
                    f"Open 'My Tickets → Ticket Details' to view and copy your secure LAPS password. "
                    f"The password expires in 15 minutes."
                )
            )
            log_rbac_event(
                user=admin_name,
                role=current_user.role,
                action="laps_access_granted",
                ticket_id=ticket_id,
                old_state=old_status,
                new_state=new_status,
                details={
                    "action": "admin_approve",
                    "laps_audit_id": ticket.laps_audit_id,
                    "manager_approver": manager_name,
                    "admin_approver": admin_name,
                    "expires_minutes": 15,
                    "note": request.note or ""
                }
            )
            db.commit()
        except Exception as _audit_err:
            logger.warning("admin_approve: audit/notification write failed (non-critical, LAPS already granted): %s", _audit_err)
            try:
                db.rollback()
            except Exception:
                pass

    # Update in-memory ticket lifecycle store for synchronization
    try:
        import app.services.ticket_lifecycle_service as tls
        if ticket_id in tls._lifecycle_store:
            tls._lifecycle_store[ticket_id]["state"] = new_status
            tls._lifecycle_store[ticket_id]["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            tls._lifecycle_store[ticket_id]["history"].append({
                "from_state": old_status,
                "to_state": new_status,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "note": request.note or f"Action: {action}"
            })
    except Exception as e:
        logger.warning("Failed to sync ticket lifecycle in-memory store: %s", e)

    return {
        "message": f"Action '{request.action}' processed successfully.",
        "ticket_id": ticket_id,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_team": ticket.assigned_team,
        "sla_hours": ticket.sla_hours
    }


class CommentCreateRequest(BaseModel):
    text: str
    is_internal: bool = False


@app.post("/tickets/{ticket_id}/comments")
def post_comment(
    ticket_id: str,
    request: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    try:
        comment = WorkflowService.add_comment(
            db=db,
            ticket_id=ticket_id,
            author=current_user.username,
            text=request.text,
            is_internal=request.is_internal,
            role=current_user.role
        )
        db.commit()
        return {
            "id": comment.id,
            "ticket_id": comment.ticket_id,
            "author": comment.author,
            "text": comment.text,
            "is_internal": comment.is_internal,
            "created_at": comment.created_at.isoformat() + "Z"
        }
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tickets/{ticket_id}/comments")
def get_comments(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    comments = WorkflowService.get_comments(db, ticket_id, current_user.role)
    return [
        {
            "id": c.id,
            "ticket_id": c.ticket_id,
            "author": c.author,
            "text": c.text,
            "is_internal": c.is_internal,
            "created_at": c.created_at.isoformat() + "Z"
        }
        for c in comments
    ]


@app.get("/tickets/{ticket_id}/details")
def get_ticket_details(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/tickets/%s/details': Fetching full details for user %s", ticket_id, current_user.username)
    from app.database.models.ticket import Ticket
    from app.database.models.audit_log import AuditLog
    from app.database.models.rbac_audit_log import RbacAuditLog
    from app.database.models.notification import Notification
    from app.database.models.conversation import Conversation
    from app.database.models.agent_trace import AgentTrace
    from app.database.models.approval_history import ApprovalHistory
    from app.database.models.action_history import ActionHistory
    from app.database.models.sla_audit_event import SlaAuditEvent
    from app.database.models.sla_escalation_history import SlaEscalationHistory
    from app.services.sla_escalation_service import compute_sla_status

    # 1. Fetch Ticket
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")

    # Self-healing LAPS Password Expiration Check
    laps_password = None
    laps_active = False
    laps_time_left = 0
    if getattr(ticket, "laps_active", False) and getattr(ticket, "laps_expiration", None):
        import datetime
        now = datetime.datetime.utcnow()
        if now > ticket.laps_expiration:
            ticket.laps_active = False
            from app.services.timeline_service import TimelineService
            TimelineService.log_event(
                db=db,
                ticket_id=ticket.ticket_id,
                event_type="LAPS_EXPIRED",
                actor="system",
                action="expire laps",
                description="Temporary privilege expired."
            )
            db.commit()
        else:
            laps_password = ticket.laps_password
            laps_active = True
            laps_time_left = int((ticket.laps_expiration - now).total_seconds())

    # RBAC: Employee can only see their own tickets
    if current_user.role not in ("ADMIN", "MANAGER") and ticket.created_by != current_user.username:
        raise HTTPException(status_code=403, detail="Access denied to this ticket's details.")

    # 2. Find associated Session ID via AuditLog
    audit_record = db.query(AuditLog).filter(AuditLog.ticket_id == ticket_id).first()
    session_id = audit_record.session_id if audit_record else None

    # Fallback to checking RbacAuditLog details or session_id
    if not session_id:
        rbac_record = db.query(RbacAuditLog).filter(RbacAuditLog.ticket_id == ticket_id).first()
        if rbac_record:
            details_str = rbac_record.details
            if details_str:
                try:
                    import json
                    details_dict = json.loads(details_str)
                    session_id = details_dict.get("session_id")
                except Exception:
                    pass

    # 3. Requester Information
    creator_username = ticket.created_by or "employee"
    creator_user = db.query(User).filter(User.username == creator_username).first()
    
    PROFILES = {
        "employee": {
            "name": "Rahul Sharma",
            "department": "Manufacturing",
            "location": "Pune",
            "email": "rahul.sharma@bridgestone.com",
            "role": "EMPLOYEE",
            "device": "BS-EMP-WS09",
            "operating_system": "Windows 11 Enterprise"
        },
        "manager": {
            "name": "Priya Verma",
            "department": "Finance",
            "location": "Indore",
            "email": "priya.verma@bridgestone.com",
            "role": "MANAGER",
            "device": "BS-MGR-LAP8",
            "operating_system": "macOS Sonoma"
        },
        "admin": {
            "name": "Amit Patel",
            "department": "IT Operations",
            "location": "Chennai",
            "email": "amit.patel@bridgestone.com",
            "role": "ADMIN",
            "device": "BS-ADM-SRV3",
            "operating_system": "Windows Server 2022"
        }
    }
    
    if creator_username in PROFILES:
        req_profile = PROFILES[creator_username]
    elif creator_user:
        req_profile = {
            "name": "Neha Singh",
            "department": "HR",
            "location": "Gurugram",
            "email": creator_user.email,
            "role": creator_user.role,
            "device": "BS-USER-LAP",
            "operating_system": "Windows 11 Enterprise"
        }
    else:
        req_profile = {
            "name": "Neha Singh",
            "department": "HR",
            "location": "Gurugram",
            "email": f"{creator_username}@bridgestone.com",
            "role": "EMPLOYEE",
            "device": "BS-USER-LAP",
            "operating_system": "Windows 11 Enterprise"
        }

    # 4. Assignment Information
    assigned_team = ticket.assigned_team or "Helpdesk"
    engineers = {
        "Network": "Rahul Sharma (NetOps)",
        "Helpdesk": "Neha Singh (Helpdesk L2)",
        "Sysadmin": "Amit Patel (SysOps)",
        "Security": "Priya Verma (SecOps)",
        "Hardware": "Neha Singh (Hardware Desk)",
        "General": "IT Operations Queue Manager"
    }
    assigned_engineer = ticket.assigned_engineer or engineers.get(assigned_team, "Neha Singh (Helpdesk L2)")
    
    # 5. SLA info
    sla_info = compute_sla_status(ticket)

    # 6. Timeline Events
    timeline = []
    
    # A. Add ticket created event
    timeline.append({
        "timestamp": ticket.created_at.isoformat() + "Z",
        "title": "Ticket Created",
        "description": f"Ticket created by {creator_username}. Category: {ticket.category}.",
        "type": "created"
    })

    # B. Add RBAC Audit events
    rbac_logs = db.query(RbacAuditLog).filter(RbacAuditLog.ticket_id == ticket_id).all()
    for log in rbac_logs:
        if log.action == "create_ticket":
            continue
        
        title = "Ticket Activity"
        if log.action == "add_internal_note":
            title = "Internal Note Added"
        elif log.action == "update_ticket_lifecycle":
            title = f"Lifecycle Status: {log.new_state}"
        elif log.action == "change_priority":
            title = f"Priority Changed: {log.new_state}"
        elif log.action == "escalate_ticket":
            title = f"SLA Escalated: {log.new_state}"

        desc = log.details or ""
        if desc:
            try:
                import json
                parsed_det = json.loads(desc)
                if isinstance(parsed_det, dict) and "note" in parsed_det:
                    desc = parsed_det["note"]
            except Exception:
                pass

        timeline.append({
            "timestamp": log.timestamp.isoformat() + "Z",
            "title": title,
            "description": desc or f"Action: {log.action} by {log.user}.",
            "type": "audit",
            "user": log.user,
            "role": log.role,
            "action": log.action
        })

    # C. Add SLA warnings and breaches
    sla_audits = db.query(SlaAuditEvent).filter(SlaAuditEvent.ticket_id == ticket_id).all()
    for evt in sla_audits:
        timeline.append({
            "timestamp": evt.created_at.isoformat() + "Z",
            "title": f"SLA Event: {evt.event_type}",
            "description": f"SLA monitor state changed to {evt.event_type}.",
            "type": "sla"
        })

    sla_esc_hist = db.query(SlaEscalationHistory).filter(SlaEscalationHistory.ticket_id == ticket_id).all()
    for esc in sla_esc_hist:
        timeline.append({
            "timestamp": esc.created_at.isoformat() + "Z",
            "title": f"SLA Escalation Level {esc.level}",
            "description": esc.reason,
            "type": "sla_escalation"
        })

    # D. Add Notifications
    notifs = db.query(Notification).filter(Notification.ticket_id == ticket_id).all()
    for n in notifs:
        timeline.append({
            "timestamp": n.created_at.isoformat() + "Z",
            "title": "Notification Dispatched",
            "description": f"Sent to {n.recipient}: {n.message}",
            "type": "notification"
        })

    # E. Add ServiceNow Operational Workflow Timeline events
    try:
        from app.database.models.workflow_models import TicketTimeline
        workflow_timeline = db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).all()
        for evt in workflow_timeline:
            timeline.append({
                "timestamp": evt.created_at.isoformat() + "Z",
                "title": evt.event_type.replace("_", " ").title(),
                "description": evt.description,
                "type": "workflow",
                "user": evt.actor,
                "role": "SYSTEM" if evt.actor == "system" else "SUPPORT",
                "action": evt.action
            })
    except Exception as e:
        logger.error("Failed to load workflow timeline events for ticket details: %s", e)

    # Sort timeline events chronologically
    timeline.sort(key=lambda x: x["timestamp"])

    # Filter timeline events for employee privacy
    filtered_timeline = []
    for evt in timeline:
        if current_user.role == "EMPLOYEE":
            t_title = str(evt.get("title", "")).lower()
            t_type = str(evt.get("type", "")).lower()
            t_action = str(evt.get("action", "")).lower()
            t_desc = str(evt.get("description", "")).lower()
            
            # Filter internal events
            if "internal note" in t_title or "work note" in t_title or t_type == "note_added" or t_action == "add_internal_note" or "confidential" in t_desc:
                continue
        filtered_timeline.append(evt)

    # 7. Conversations
    chat_history = []
    if session_id:
        turns = db.query(Conversation).filter(Conversation.session_id == session_id).order_by(Conversation.id.asc()).all()
        for t in turns:
            chat_history.append({
                "sender": "user",
                "text": t.user_message,
                "timestamp": t.created_at.isoformat() + "Z"
            })
            chat_history.append({
                "sender": "agent",
                "text": t.agent_response,
                "timestamp": t.created_at.isoformat() + "Z"
            })

    # 8. AI Diagnosis
    ai_diagnosis = None
    tool_chain = []
    if session_id:
        trace = db.query(AgentTrace).filter(AgentTrace.session_id == session_id).first()
        if trace and trace.output_data:
            out_data = trace.output_data
            if isinstance(out_data, dict):
                ai_diagnosis = {
                    "summary": out_data.get("summary") or out_data.get("thought") or f"AI analyzed {ticket.category} incident.",
                    "root_cause": out_data.get("root_cause") or "Undetermined root cause.",
                    "troubleshooting_steps": out_data.get("steps") or out_data.get("troubleshooting") or "Performed initial diagnostics check.",
                    "tools_executed": out_data.get("tools") or [],
                    "confidence_score": out_data.get("confidence") or 85
                }
                tool_chain = out_data.get("tools", [])
    
    fallback_diag = {
        "VPN": {
            "summary": "VPN connection gateway timeout (Error 809). AI attempted ping tests and routing validation.",
            "root_cause": "Congested remote access gateway or stale firewall tunnel state.",
            "troubleshooting_steps": "1. Verified gateway ping response.\n2. Polled Entra ID authentication status.\n3. Verified user session active state.",
            "tools_executed": ["ping_vpn_gateway", "check_ad_session"],
            "confidence_score": 92
        },
        "Password": {
            "summary": "AD credentials lockout. AI triggered AD lockout query and unlocked user record.",
            "root_cause": "Brute lock triggered by multiple failed password attempts on workstation.",
            "troubleshooting_steps": "1. Inspected domain controller lockout state.\n2. Reset lockout flags in AD.\n3. Initiated security notification flow.",
            "tools_executed": ["check_lockout_status", "unlock_ad_user"],
            "confidence_score": 98
        },
        "Software": {
            "summary": "Software licensing provision request for Microsoft Visio.",
            "root_cause": "Visio deployment package lacks valid license allocation.",
            "troubleshooting_steps": "1. Queried licensing server inventory.\n2. Dispatched approval request to Manager.",
            "tools_executed": ["check_license_availability", "request_manager_approval"],
            "confidence_score": 90
        },
        "Outlook": {
            "summary": "Outlook crash on launch. AI analyzed local cache registry key.",
            "root_cause": "Corrupted local OST file state or add-in incompatibility.",
            "troubleshooting_steps": "1. Reset outlook safe-mode profiles.\n2. Dispatched OST repair request.",
            "tools_executed": ["repair_outlook_profile"],
            "confidence_score": 87
        },
        "SAP": {
            "summary": "SAP ERP application throwing gateway time-outs on ordering systems.",
            "root_cause": "Congested app server queue or offline database middleware connectivity.",
            "troubleshooting_steps": "1. Polled application server status metrics.\n2. Tested DB listener ports.",
            "tools_executed": ["ping_sap_server", "check_db_listener"],
            "confidence_score": 94
        },
        "Network": {
            "summary": "Warehouse network switch offline. Switch ports reporting link down.",
            "root_cause": "Switch port hardware failure or fiber cable link disconnection.",
            "troubleshooting_steps": "1. Polled SNMP interfaces.\n2. Verified upstream gateway route ping.",
            "tools_executed": ["snmp_poll_switch", "ping_gateway"],
            "confidence_score": 91
        },
        "Hardware": {
            "summary": "Laptop hardware screen issue. Screen goes black on lid articulation.",
            "root_cause": "Physical display hinge ribbon cable damaged.",
            "troubleshooting_steps": "1. Recommended physical hardware desk drop-off.\n2. Initiated device replacement request in ServiceNow.",
            "tools_executed": ["schedule_hardware_repair"],
            "confidence_score": 96
        }
    }

    if not ai_diagnosis:
        ai_diagnosis = fallback_diag.get(ticket.category, {
            "summary": f"Incident logged in category {ticket.category}. AI initialized basic diagnostic trace.",
            "root_cause": "Undetermined software or hardware incident.",
            "troubleshooting_steps": "1. Logged ticket details.\n2. Assigned to support queue.",
            "tools_executed": ["create_ticket"],
            "confidence_score": 85
        })

    # Resolve device/OS dynamically from trace outputs if available
    device = None
    operating_system = None
    if session_id:
        trace = db.query(AgentTrace).filter(AgentTrace.session_id == session_id).first()
        if trace and trace.output_data:
            out_data = trace.output_data
            if isinstance(out_data, dict):
                for tool in out_data.get("tools", []):
                    if tool.get("tool_name") == "system_tools":
                        td = tool.get("data", {})
                        device = td.get("hostname")
                        operating_system = td.get("system_info")

    if not device:
        device = req_profile.get("device", "BS-USER-LAP")
    if not operating_system:
        operating_system = req_profile.get("operating_system", "Windows 11 Enterprise")

    req_profile["device"] = device
    req_profile["operating_system"] = operating_system

    # 9. Related Objects Links
    related_approvals = []
    if session_id:
        apps = db.query(ApprovalHistory).filter(ApprovalHistory.session_id == session_id).all()
        for a in apps:
            related_approvals.append({
                "approval_id": f"APPROVAL-00{a.id}",
                "action": a.recommended_action,
                "status": a.approval_status,
                "created_at": a.created_at.isoformat() + "Z"
            })
    
    related_requests = []
    if session_id:
        reqs = db.query(ActionHistory).filter(ActionHistory.request_id.like(f"%{session_id[-8:]}%")).all()
        for r in reqs:
            related_requests.append({
                "request_id": r.request_id,
                "servicenow_id": r.servicenow_id or f"REQ0000{r.id}",
                "action": r.action_type,
                "status": r.status,
                "created_at": r.created_at.isoformat() + "Z"
            })
            
    if not related_requests and ticket.servicenow_id:
        related_requests.append({
            "request_id": f"REQ-{ticket.ticket_id[-6:]}",
            "servicenow_id": ticket.servicenow_id,
            "action": f"ServiceNow Sync ({ticket.category})",
            "status": "SUCCESS" if ticket.status in ("RESOLVED", "CLOSED") else "RUNNING",
            "created_at": ticket.created_at.isoformat() + "Z"
        })

    # Retrieve and format comments separation
    from app.services.workflow_service import WorkflowService
    comments = WorkflowService.get_comments(db, ticket_id, current_user.role)
    customer_comments = [
        {
            "id": c.id,
            "author": c.author,
            "text": c.text,
            "created_at": c.created_at.isoformat() + "Z"
        }
        for c in comments if not c.is_internal
    ]
    internal_notes = [
        {
            "id": c.id,
            "author": c.author,
            "text": c.text,
            "created_at": c.created_at.isoformat() + "Z"
        }
        for c in comments if c.is_internal
    ]

    # Generate Dynamic Engineer Summary (Markdown report)
    from app.agents.engineer_summary_agent import EngineerSummaryAgent
    summary_agent = EngineerSummaryAgent()
    from app.agents.hypothesis_tracker_agent import HypothesisTrackerAgent
    tracker = HypothesisTrackerAgent()
    hypotheses = tracker._update_rule_based(ticket.category, tool_chain if tool_chain else [{"tool_name": "system_tools", "status": "SUCCESS"}])
    engineer_summary = summary_agent.generate_summary(
        category=ticket.category,
        tool_chain=tool_chain if tool_chain else [{"tool_name": "system_tools", "status": "SUCCESS", "data": {"status": "SUCCESS"}}],
        hypotheses=hypotheses,
        user_message=ticket.description or ""
    )

    # ── CONVERSATION SUMMARY GENERATOR ──────────────────────────────────────────
    questions_asked = []
    for msg in chat_history:
        if msg["sender"] == "agent":
            text = msg["text"]
            if "?" in text or "[A]" in text or "select" in text.lower() or "please choose" in text.lower():
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                for line in lines:
                    if line.endswith("?") or "[A]" in line or "select" in line.lower():
                        questions_asked.append(line)
                        break

    if not questions_asked:
        questions_asked = ["Verified customer identity and category classification."]

    tools_run_names = []
    tool_results_list = []
    if tool_chain:
        for t in tool_chain:
            name = t.get("tool_name", "unknown_tool")
            status = t.get("status", "SUCCESS")
            tools_run_names.append(name)
            tool_results_list.append(f"{name}: {status}")
    else:
        diag = fallback_diag.get(ticket.category, ai_diagnosis)
        tools_run_names = diag.get("tools_executed", ["create_ticket"])
        tool_results_list = [f"{t}: SUCCESS" for t in tools_run_names]

    rec_next_step = "Review ticket diagnosis and assign L2 engineer."
    if ticket.category == "VPN":
        rec_next_step = "Reset user remote access gateway credentials."
    elif ticket.category == "Password":
        rec_next_step = "Verify user status in Active Directory and reset account lock flags."
    elif ticket.category == "Software":
        rec_next_step = "Verify licensing compliance and push Visio deployment package."
    elif ticket.category == "Outlook":
        rec_next_step = "Repair corrupted Outlook OST profile file cache."
    elif ticket.category == "SAP":
        rec_next_step = "Verify db listener port status and clear user PRD lock table."

    conversation_summary = {
        "issue": f"{ticket.category} Access Restorations",
        "symptoms": ticket.issue_description or ticket.description or "User reported connectivity or system access difficulty.",
        "questions_asked": questions_asked,
        "tools_executed": tools_run_names,
        "results": tool_results_list,
        "current_status": ticket.status,
        "recommended_next_step": rec_next_step
    }

    return {
        "ticket": {
            "ticket_id": ticket.ticket_id,
            "category": ticket.category,
            "description": ticket.description,
            "issue_description": ticket.issue_description,
            "assigned_team": ticket.assigned_team,
            "priority": ticket.priority,
            "sla_hours": ticket.sla_hours,
            "status": ticket.status,
            "servicenow_id": ticket.servicenow_id,
            "created_by": ticket.created_by,
            "created_at": ticket.created_at.isoformat() + "Z",
            "updated_at": (ticket.resolved_at or ticket.closed_at or ticket.reopened_at or ticket.created_at).isoformat() + "Z",
            "sla_state": ticket.sla_state or "HEALTHY",
            "sla_breached": ticket.sla_breached or False,
            "sla_breached_at": ticket.sla_breached_at.isoformat() + "Z" if ticket.sla_breached_at else None,
            "assigned_engineer": ticket.assigned_engineer,
            "reopen_count": ticket.reopen_count or 0,
            "reopened_at": ticket.reopened_at.isoformat() + "Z" if ticket.reopened_at else None,
            "reopened_by": ticket.reopened_by,
            # ITSM workflow fields — needed for approval banners and LAPS panel
            "request_type": ticket.request_type,
            "approval_status": ticket.approval_status,
            "manager": ticket.manager,
            # LAPS simulation fields
            "laps_password": laps_password,
            "laps_active": laps_active,
            "laps_time_left": laps_time_left,
            "laps_audit_id": ticket.laps_audit_id
        },
        "session_id": session_id,
        "requester": req_profile,
        "assignment": {
            "assigned_team": assigned_team,
            "assigned_engineer": assigned_engineer,
            "current_owner": assigned_engineer if ticket.status != "OPEN" else "IT Agent (Auto-pilot)",
            "queue": f"{assigned_team} Tier-2 Queue"
        },
        "sla": sla_info,
        "timeline": filtered_timeline,
        "conversation": chat_history,
        "ai_diagnosis": {
            "summary": ai_diagnosis["summary"] if isinstance(ai_diagnosis, dict) else "Initial diagnostics trace.",
            "root_cause": ai_diagnosis["root_cause"] if isinstance(ai_diagnosis, dict) else "Undetermined root cause.",
            "troubleshooting_steps": ai_diagnosis["troubleshooting_steps"] if isinstance(ai_diagnosis, dict) else "No steps run.",
            "tools_executed": tools_run_names,
            "confidence_score": ai_diagnosis["confidence_score"] if isinstance(ai_diagnosis, dict) else 85,
            "engineer_summary": engineer_summary
        },
        "conversation_summary": conversation_summary,
        "comments": customer_comments,
        "internal_notes": internal_notes,
        "approval_required": len(related_approvals) > 0,
        "approval_status": related_approvals[0]["status"] if related_approvals else "PENDING",
        "related": {
            "approvals": related_approvals,
            "requests": related_requests
        }
    }


@app.get("/api/tickets/{ticket_id}/ai-diagnosis")
@app.get("/tickets/{ticket_id}/ai-diagnosis")
def get_ai_diagnosis(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/tickets/%s/ai-diagnosis': Fetching AI diagnosis", ticket_id)
    from app.database.models.ticket import Ticket
    from app.database.models.audit_log import AuditLog
    from app.database.models.rbac_audit_log import RbacAuditLog
    from app.services.conversation_service import conversations

    # 1. Fetch Ticket
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")

    # RBAC: Employee can only see their own tickets
    if current_user.role not in ("ADMIN", "MANAGER") and ticket.created_by != current_user.username:
        raise HTTPException(status_code=403, detail="Access denied to this ticket's AI diagnosis.")

    # 2. Find associated Session ID
    audit_record = db.query(AuditLog).filter(AuditLog.ticket_id == ticket_id).first()
    session_id = audit_record.session_id if audit_record else None

    if not session_id:
        rbac_record = db.query(RbacAuditLog).filter(RbacAuditLog.ticket_id == ticket_id).first()
        if rbac_record and rbac_record.details:
            try:
                import json
                details_dict = json.loads(rbac_record.details)
                session_id = details_dict.get("session_id")
            except Exception:
                pass

    # Initialize default/fallback values
    engineer_summary = None
    tool_chain = []
    hypothesis_tracker = []
    root_cause_confidence = 0.85

    # 3. Retrieve from in-memory conversations if available
    if session_id and session_id in conversations:
        conv_state = conversations[session_id]
        engineer_summary = getattr(conv_state, "engineer_summary", None)
        tool_chain = getattr(conv_state, "tool_chain", [])
        hypothesis_tracker = getattr(conv_state, "hypothesis_tracker", [])

    # 4. Generate dynamic fallback if still empty (so the UI never looks blank)
    if not engineer_summary:
        from app.agents.engineer_summary_agent import EngineerSummaryAgent
        from app.agents.hypothesis_tracker_agent import HypothesisTrackerAgent
        
        # Build list of tools executed based on category to populate tool chain
        dummy_msg = ticket.description or ""
        dummy_chain = []
        if ticket.category == "VPN":
            dummy_chain = [
                {"tool_name": "vpn_tools", "status": "SUCCESS", "data": {"vpn_gateway": "ONLINE", "user_access": "DISABLED", "latency_ms": 25, "status": "ONLINE"}}
            ]
        elif ticket.category == "OUTLOOK":
            dummy_chain = [
                {"tool_name": "outlook_tools", "status": "SUCCESS", "data": {"mailbox_status": "ACTIVE", "exchange_server": "ONLINE", "exchange_latency": 15}}
            ]
        elif ticket.category == "NETWORK":
            dummy_chain = [
                {"tool_name": "network_tools", "status": "SUCCESS", "data": {"network_status": "ONLINE", "wifi_status": "ONLINE", "packet_loss": 0}}
            ]
        else:
            dummy_chain = [
                {"tool_name": "system_tools", "status": "SUCCESS", "data": {"system_info": "Windows 11", "hostname": "BS-USER-LAP", "ip_address": "10.180.24.45"}}
            ]
            
        tracker = HypothesisTrackerAgent()
        dummy_hypotheses = tracker._update_rule_based(ticket.category, dummy_chain)
        
        summary_agent = EngineerSummaryAgent()
        engineer_summary = summary_agent._generate_fallback(
            ticket.category,
            dummy_chain,
            dummy_hypotheses,
            dummy_msg
        )
        tool_chain = dummy_chain
        hypothesis_tracker = dummy_hypotheses

    # Find highest confidence from hypothesis tracker
    if hypothesis_tracker:
        try:
            root_cause_confidence = max(float(h.get("confidence", 0.5)) for h in hypothesis_tracker)
        except Exception:
            pass

    return {
        "engineer_summary": engineer_summary,
        "tool_chain": tool_chain,
        "hypothesis_tracker": hypothesis_tracker,
        "root_cause_confidence": root_cause_confidence
    }


@app.get("/service-catalog")
def list_service_catalog(current_user: User = Depends(get_current_user)):
    from app.services.catalog_service import get_service_catalog
    logger.info("FastAPI Endpoint GET '/service-catalog': Fetching catalog items for user %s", current_user.username)
    return get_service_catalog()

class ServiceRequestCreateRequest(BaseModel):
    service_id: str
    details: dict

@app.post("/service-requests")
def make_service_request(request: ServiceRequestCreateRequest, current_user: User = Depends(get_current_user)):
    from app.services.catalog_service import create_service_request
    logger.info("FastAPI Endpoint POST '/service-requests': Creating request for service_id=%s, user=%s", request.service_id, current_user.username)
    try:
        return create_service_request(request.service_id, current_user.username, request.details)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/service-requests")
def list_service_requests(current_user: User = Depends(get_current_user)):
    from app.services.catalog_service import get_service_requests
    logger.info("FastAPI Endpoint GET '/service-requests': Fetching requests for user %s, role %s", current_user.username, current_user.role)
    return get_service_requests(username=current_user.username, role=current_user.role)

@app.get("/service-requests/{request_id}/details")
def service_request_details(request_id: str, current_user: User = Depends(get_current_user)):
    from app.services.catalog_service import get_service_request_details
    logger.info("FastAPI Endpoint GET '/service-requests/%s/details': Fetching details for user %s", request_id, current_user.username)
    details = get_service_request_details(request_id)
    if not details:
        raise HTTPException(status_code=404, detail=f"Service request '{request_id}' not found.")
    if current_user.role not in ("ADMIN", "MANAGER") and details.get("requested_by") != current_user.username:
        raise HTTPException(status_code=403, detail="Not authorized to view this service request.")
    return details

class ServiceRequestActionRequest(BaseModel):
    action: str
    note: str | None = None

@app.post("/service-requests/{request_id}/action")
def run_service_request_action(
    request_id: str,
    request: ServiceRequestActionRequest,
    current_user: User = Depends(get_current_user)
):
    from app.services.catalog_service import perform_request_action
    logger.info("FastAPI Endpoint POST '/service-requests/%s/action': Action=%s, user=%s", request_id, request.action, current_user.username)
    try:
        res = perform_request_action(
            request_id=request_id,
            action=request.action,
            user=current_user.username,
            role=current_user.role,
            note=request.note
        )
        if not res:
            raise HTTPException(status_code=404, detail=f"Service request '{request_id}' not found.")
        return res
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/notifications")
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/notifications': Fetching notifications for user %s", current_user.username)
    from app.services.notification_service import NotificationService
    return NotificationService.get_user_notifications(
        user_id=current_user.username,
        user_role=current_user.role,
        unread_only=False,
        db=db
    )

@app.get("/notifications/unread")
def list_unread_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/notifications/unread': Fetching unread notifications for user %s", current_user.username)
    from app.services.notification_service import NotificationService
    unread_notifs = NotificationService.get_user_notifications(
        user_id=current_user.username,
        user_role=current_user.role,
        unread_only=True,
        db=db
    )
    return {
        "unread_count": len(unread_notifs),
        "notifications": unread_notifs
    }

@app.post("/notifications/read/{notification_id}")
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint POST '/notifications/read/%s': User %s marking as read", notification_id, current_user.username)
    from app.services.notification_service import NotificationService
    try:
        nid = int(notification_id)
    except ValueError:
        nid = notification_id
    success = NotificationService.mark_as_read(notification_id=nid, user_id=current_user.username, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read", "id": notification_id}

@app.post("/notifications/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint POST '/notifications/read-all': User %s marking all as read", current_user.username)
    from app.services.notification_service import NotificationService
    count = NotificationService.mark_all_as_read(user_id=current_user.username, user_role=current_user.role, db=db)
    return {"message": f"Marked {count} notifications as read", "count": count}

@app.delete("/notifications/{notification_id}")
def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint DELETE '/notifications/%s': User %s deleting notification", notification_id, current_user.username)
    from app.services.notification_service import NotificationService
    try:
        nid = int(notification_id)
    except ValueError:
        nid = notification_id
    success = NotificationService.delete_notification(notification_id=nid, user_id=current_user.username, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification deleted", "id": notification_id}

breached_tickets_set = set()

@app.get("/sla")
def list_sla(current_user: User = Depends(get_current_user)):
    logger.info("FastAPI Endpoint GET '/sla': Fetching SLA metadata")
    open_tickets = [t for t in get_all_tickets() if t.get("status") == "OPEN"]
    
    # Dynamic SLA Breach Detection
    from datetime import datetime
    for t in open_tickets:
        created_at_str = t.get("created_at")
        if created_at_str:
            try:
                # Strip the Z suffix and parse
                dt_str = created_at_str.replace("Z", "+00:00")
                created_time = datetime.fromisoformat(dt_str).replace(tzinfo=None)
                elapsed = (datetime.utcnow() - created_time).total_seconds() / 3600.0
                sla_hours = t.get("sla_hours", 24)
                if elapsed > sla_hours:
                    t_id = t.get("ticket_id")
                    if t_id not in breached_tickets_set:
                        breached_tickets_set.add(t_id)
                        try:
                            from app.core.metrics import BUSINESS_SLA_BREACHES_TOTAL
                            BUSINESS_SLA_BREACHES_TOTAL.inc()
                        except Exception:
                            pass
            except Exception as e:
                logger.error("Failed to parse ticket created_at or check SLA breach: %s", e)

    if current_user.role not in ("ADMIN", "MANAGER"):
        # Filter for employee's own tickets
        open_tickets = [t for t in open_tickets if t.get("created_by") == current_user.username]
    return [
        {
            "ticket_id": t.get("ticket_id"),
            "priority": t.get("priority"),
            "sla_hours": t.get("sla_hours")
        }
        for t in open_tickets
    ]


# ── SLA Escalation Engine endpoints ────────────────────────────────────────

@app.get("/sla/dashboard-metrics")
def sla_dashboard_metrics(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    """
    Returns aggregated SLA state counts and compliance percentage.
    Data powered by SlaEscalationService — reflects DB-persisted sla_state.
    """
    logger.info("FastAPI Endpoint GET '/sla/dashboard-metrics': Requested by user %s", current_user.username)
    from app.services.sla_escalation_service import get_dashboard_metrics
    return get_dashboard_metrics()


@app.get("/sla/escalations")
def sla_escalation_history(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    """
    Returns the full SLA escalation history list (all tickets, newest first).
    Useful for the Admin Console SLA Escalations section.
    """
    logger.info("FastAPI Endpoint GET '/sla/escalations': Requested by user %s", current_user.username)
    from app.services.sla_escalation_service import get_escalation_history
    return get_escalation_history()


@app.get("/sla/ticket/{ticket_id}")
def sla_ticket_status(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Returns real-time SLA status for a specific ticket.
    EMPLOYEEs can only view their own tickets; ADMIN/MANAGER see all.
    """
    logger.info(
        "FastAPI Endpoint GET '/sla/ticket/%s': Requested by user %s",
        ticket_id, current_user.username,
    )
    from app.services.sla_escalation_service import get_sla_status_for_ticket
    from app.database.models.ticket import Ticket
    from app.database.session import get_db as _get_db

    # RBAC: employees may only query their own tickets
    if current_user.role not in ("ADMIN", "MANAGER"):
        with _get_db() as db:
            t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
            if not t or t.created_by != current_user.username:
                raise HTTPException(status_code=403, detail="Access denied to this ticket's SLA data.")

    result = get_sla_status_for_ticket(ticket_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")
    return result


@app.get("/servicenow/incidents")
def get_servicenow_incidents(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/servicenow/incidents': Fetching ServiceNow incidents")
    return snow_adapter.get_all_incidents()

@app.get("/servicenow/incidents/{id}")
def get_servicenow_incident_by_id(id: str, current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/servicenow/incidents/%s': Fetching specific incident", id)
    try:
        return snow_adapter.get_incident(id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"ServiceNow Incident {id} not found.")

@app.post("/servicenow/incidents")
def create_servicenow_incident(request: IncidentCreateRequest, current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint POST '/servicenow/incidents': Manually creating incident")
    return snow_adapter.create_incident(
        category=request.category,
        description=request.description,
        assignment_group=request.assignment_group
    )

@app.get("/servicenow/requests")
def get_servicenow_requests(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/servicenow/requests': Fetching ServiceNow service requests")
    return snow_adapter.get_all_requests()

@app.get("/servicenow/requests/{id}")
def get_servicenow_request_by_id(id: str, current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/servicenow/requests/%s': Fetching specific service request", id)
    try:
        return snow_adapter.get_request(id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"ServiceNow Service Request {id} not found.")

@app.get("/microsoftgraph/users")
def get_microsoft_graph_users(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/microsoftgraph/users': Fetching Microsoft Graph users")
    return graph_adapter.get_all_users()

@app.get("/microsoftgraph/groups")
def get_microsoft_graph_groups(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/microsoftgraph/groups': Fetching Microsoft Graph groups")
    return graph_adapter.get_all_groups()

@app.get("/entra/users")
def get_entra_users(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/entra/users': Fetching Entra ID users")
    return ad_adapter.get_all_users()

@app.get("/entra/groups")
def get_entra_groups(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/entra/groups': Fetching Entra ID groups")
    return ad_adapter.get_all_groups()

@app.get("/entra/stats")
def get_entra_stats(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/entra/stats': Fetching Entra ID monitoring stats")
    return ad_adapter.get_monitoring_stats()


@app.get("/actions")
def list_actions(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/actions': Fetching all logged actions for user %s", current_user.username)
    return get_all_actions_history()

@app.get("/audit-logs")
def list_audit_logs(current_user: User = Depends(RoleChecker(["ADMIN"]))):
    logger.info("FastAPI Endpoint GET '/audit-logs': Fetching all audit logs for user %s", current_user.username)
    return get_all_audit_logs()

@app.get("/approvals")
def list_approvals(current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))):
    logger.info("FastAPI Endpoint GET '/approvals': Fetching all approvals history for user %s", current_user.username)
    return get_all_approvals_history()

@app.get("/agent-traces")
def list_agent_traces(current_user: User = Depends(RoleChecker(["ADMIN"]))):
    logger.info("FastAPI Endpoint GET '/agent-traces': Fetching all agent traces for user %s", current_user.username)
    return get_all_agent_traces()

# Protected admin security logs endpoint
@app.get("/admin/security-logs")
def list_security_logs(current_user: User = Depends(RoleChecker(["ADMIN"]))):
    logger.info("FastAPI Endpoint GET '/admin/security-logs': Fetching security events for user %s", current_user.username)
    from app.services.security_service import get_all_security_events
    return get_all_security_events()


# ── Enterprise RBAC Audit Log endpoints ─────────────────────────────────────

@app.get("/rbac-audit-logs")
def list_rbac_audit_logs(current_user: User = Depends(RoleChecker(["ADMIN"]))):
    """Returns all RBAC audit events. ADMIN only."""
    logger.info(
        "FastAPI Endpoint GET '/rbac-audit-logs': Fetching all RBAC audit logs for user %s",
        current_user.username,
    )
    from app.services.rbac_audit_service import get_rbac_audit_logs
    return get_rbac_audit_logs()


@app.get("/rbac-audit-logs/{ticket_id}")
def list_rbac_audit_logs_by_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Returns RBAC audit events for a specific ticket. ADMIN, MANAGER, or ticket creator."""
    logger.info(
        "FastAPI Endpoint GET '/rbac-audit-logs/%s': Fetching RBAC audit logs for user %s",
        ticket_id, current_user.username,
    )
    from app.database.models.ticket import Ticket
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    
    if current_user.role not in ("ADMIN", "MANAGER") and ticket.created_by != current_user.username:
        raise HTTPException(status_code=403, detail="Access denied to this ticket's audit logs.")

    from app.services.rbac_audit_service import get_rbac_audit_logs
    return get_rbac_audit_logs(ticket_id=ticket_id)


# ── Background Job & Scheduler Lifecycle Events ───────────────────────────

@app.on_event("startup")
def startup_event():
    import os
    if os.getenv("TESTING") == "True":
        logger.info("FastAPI Startup: Testing mode active. Skipping background scheduler.")
        return
    from app.core.json_logger import setup_json_logging
    setup_json_logging(logging.INFO)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    logger.info("FastAPI Startup: Resolved Gemini model name from environment: %s", model_name)
    
    # Verify AI Provider availability
    try:
        from app.services.ai_provider import get_ai_provider
        provider = get_ai_provider()
        provider.verify()
        if not provider.is_ready():
            logger.error("FastAPI Startup ERROR: Active AI provider is not ready.")
    except Exception as e:
        logger.warning("FastAPI Startup: Failed to perform AI provider verification check: %s", e)

    logger.info("FastAPI Startup: Initializing background job scheduler.")
    from app.jobs.scheduler import init_scheduler
    init_scheduler()

@app.on_event("shutdown")
def shutdown_event():
    logger.info("FastAPI Shutdown: Stopping background job scheduler.")
    from app.jobs.scheduler import shutdown_scheduler
    shutdown_scheduler()


# ── Background Job & Scheduler API Endpoints ──────────────────────────────

@app.get("/jobs")
def list_jobs(
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db_context)
):
    """Lists all registered background jobs and their live status/schedules."""
    logger.info("FastAPI Endpoint GET '/jobs': Requested by user %s", current_user.username)
    from app.database.models.scheduled_job import ScheduledJob
    from app.jobs.scheduler import scheduler_instance
    
    jobs = db.query(ScheduledJob).all()
    response = []
    for job in jobs:
        # Check active status and live next run time from scheduler memory
        live_job = scheduler_instance.get_job(job.job_name) if scheduler_instance else None
        next_run = live_job.next_run_time.replace(tzinfo=None).isoformat() + "Z" if (live_job and live_job.next_run_time) else (job.next_run_time.isoformat() + "Z" if job.next_run_time else None)
        
        response.append({
            "job_name": job.job_name,
            "job_type": job.job_type,
            "interval_seconds": job.interval_seconds,
            "cron_expression": job.cron_expression,
            "is_enabled": job.is_enabled,
            "last_run_time": job.last_run_time.isoformat() + "Z" if job.last_run_time else None,
            "next_run_time": next_run,
            "is_active": live_job is not None
        })
    return response

@app.get("/jobs/history")
def list_jobs_history(
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db_context)
):
    """Lists the history of past background job executions."""
    logger.info("FastAPI Endpoint GET '/jobs/history': Requested by user %s", current_user.username)
    from app.database.models.scheduled_job import JobExecutionHistory
    history = db.query(JobExecutionHistory).order_by(JobExecutionHistory.started_at.desc()).limit(100).all()
    return [
        {
            "id": h.id,
            "job_name": h.job_name,
            "status": h.status,
            "started_at": h.started_at.isoformat() + "Z" if h.started_at else None,
            "completed_at": h.completed_at.isoformat() + "Z" if h.completed_at else None,
            "error_message": h.error_message
        }
        for h in history
    ]

@app.post("/jobs/run/{job_name}")
def run_job(
    job_name: str,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    """Triggers execution of a specific job immediately."""
    logger.info("FastAPI Endpoint POST '/jobs/run/%s': Requested by user %s", job_name, current_user.username)
    from app.jobs.scheduler import execute_job_manually
    success = execute_job_manually(job_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found.")
    return {"message": f"Job '{job_name}' triggered successfully."}

@app.post("/jobs/enable/{job_name}")
def enable_job(
    job_name: str,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db_context)
):
    """Enables a disabled background job and schedules it."""
    logger.info("FastAPI Endpoint POST '/jobs/enable/%s': Requested by user %s", job_name, current_user.username)
    from app.database.models.scheduled_job import ScheduledJob
    from app.jobs.scheduler import schedule_job_in_scheduler, sync_next_run_times
    
    job = db.query(ScheduledJob).filter(ScheduledJob.job_name == job_name).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found.")
        
    job.is_enabled = True
    db.commit()
    
    # Register back into scheduler
    schedule_job_in_scheduler(job)
    sync_next_run_times()
    return {"message": f"Job '{job_name}' enabled successfully."}

@app.post("/jobs/disable/{job_name}")
def disable_job(
    job_name: str,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db_context)
):
    """Disables an active background job and removes it from active schedule."""
    logger.info("FastAPI Endpoint POST '/jobs/disable/%s': Requested by user %s", job_name, current_user.username)
    from app.database.models.scheduled_job import ScheduledJob
    from app.jobs.scheduler import scheduler_instance, sync_next_run_times
    
    job = db.query(ScheduledJob).filter(ScheduledJob.job_name == job_name).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found.")
        
    job.is_enabled = False
    db.commit()
    
    # Remove from running scheduler if present
    if scheduler_instance and scheduler_instance.get_job(job_name):
        scheduler_instance.remove_job(job_name)
    sync_next_run_times()
    return {"message": f"Job '{job_name}' disabled successfully."}


# ── ServiceNow Operational Workflow Endpoints ──────────────────────────────
import json

class CommentCreate(BaseModel):
    text: str
    is_internal: bool

class CommentEdit(BaseModel):
    text: str

class AssignRequest(BaseModel):
    assigned_engineer: str
    assigned_group: str = None
    reason: str = None

class ReopenRequest(BaseModel):
    reason: str

class CsatRequest(BaseModel):
    rating: int
    feedback: str = None
    response_time_rating: int = None
    resolution_quality_rating: int = None
    would_recommend: bool = True

class ClusterFixRequest(BaseModel):
    known_fix: str

class DuplicateLinkRequest(BaseModel):
    source_ticket_id: str
    target_ticket_id: str


@app.post("/tickets/{ticket_id}/comments")
def add_ticket_comment(
    ticket_id: str,
    body: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    try:
        comment = WorkflowService.add_comment(
            db=db,
            ticket_id=ticket_id,
            author=current_user.username,
            text=body.text,
            is_internal=body.is_internal,
            role=current_user.role
        )
        db.commit()
        return {
            "id": comment.id,
            "ticket_id": comment.ticket_id,
            "author": comment.author,
            "text": comment.text,
            "is_internal": comment.is_internal,
            "created_at": comment.created_at
        }
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tickets/{ticket_id}/comments")
def get_ticket_comments(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    comments = WorkflowService.get_comments(db=db, ticket_id=ticket_id, role=current_user.role)
    return [
        {
            "id": c.id,
            "ticket_id": c.ticket_id,
            "author": c.author,
            "text": c.text,
            "is_internal": c.is_internal,
            "created_at": c.created_at,
            "edited_history": json.loads(c.edited_history) if c.edited_history else []
        }
        for c in comments
    ]

@app.put("/comments/{comment_id}")
def edit_ticket_comment(
    comment_id: int,
    body: CommentEdit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    try:
        comment = WorkflowService.edit_comment(
            db=db,
            comment_id=comment_id,
            author=current_user.username,
            new_text=body.text,
            role=current_user.role
        )
        db.commit()
        return {"message": "Comment updated successfully."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tickets/{ticket_id}/assign")
def assign_ticket(
    ticket_id: str,
    body: AssignRequest,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER", "SUPPORT", "ENGINEER"])),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    try:
        ticket = WorkflowService.assign_ticket(
            db=db,
            ticket_id=ticket_id,
            new_engineer=body.assigned_engineer,
            assigned_by=current_user.username,
            reason=body.reason,
            new_group=body.assigned_group
        )
        db.commit()
        return {"message": f"Ticket {ticket_id} successfully assigned to {body.assigned_engineer}."}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tickets/{ticket_id}/assignment-history")
def get_ticket_assignment_history(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.database.models.workflow_models import AssignmentHistory
    history = db.query(AssignmentHistory).filter(AssignmentHistory.ticket_id == ticket_id).order_by(AssignmentHistory.assigned_time.desc()).all()
    return [
        {
            "id": h.id,
            "assigned_group": h.assigned_group,
            "assigned_engineer": h.assigned_engineer,
            "assigned_by": h.assigned_by,
            "assigned_time": h.assigned_time,
            "reason": h.reason,
            "previous_engineer": h.previous_engineer,
            "new_engineer": h.new_engineer
        }
        for h in history
    ]

@app.get("/tickets/{ticket_id}/timeline")
def get_ticket_timeline(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.timeline_service import TimelineService
    timeline = TimelineService.get_timeline(db=db, ticket_id=ticket_id)
    return [
        {
            "id": t.id,
            "event_type": t.event_type,
            "actor": t.actor,
            "action": t.action,
            "description": t.description,
            "created_at": t.created_at,
            "correlation_id": t.correlation_id
        }
        for t in timeline
    ]

@app.post("/tickets/{ticket_id}/reopen")
def reopen_ticket(
    ticket_id: str,
    body: ReopenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    try:
        WorkflowService.reopen_ticket(
            db=db,
            ticket_id=ticket_id,
            reopened_by=current_user.username,
            reason=body.reason
        )
        db.commit()
        return {"message": f"Ticket {ticket_id} reopened successfully."}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tickets/{ticket_id}/csat")
def submit_ticket_csat(
    ticket_id: str,
    body: CsatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    try:
        WorkflowService.submit_csat(
            db=db,
            ticket_id=ticket_id,
            rating=body.rating,
            feedback=body.feedback,
            response_time_rating=body.response_time_rating,
            resolution_quality_rating=body.resolution_quality_rating,
            would_recommend=body.would_recommend
        )
        db.commit()
        return {"message": "CSAT survey submitted successfully."}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/dashboard/executive-metrics")
def get_executive_metrics(
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    return WorkflowService.get_executive_metrics(db=db)

@app.get("/admin/dashboard/clusters")
def get_incident_clusters(
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db_context)
):
    from app.services.cluster_service import ClusterService
    return ClusterService.get_clusters_dashboard(db=db)

@app.put("/admin/dashboard/clusters/{cluster_id}/fix")
def update_cluster_fix(
    cluster_id: int,
    body: ClusterFixRequest,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db_context)
):
    from app.services.cluster_service import ClusterService
    success = ClusterService.update_known_fix(db=db, cluster_id=cluster_id, known_fix=body.known_fix)
    if not success:
        raise HTTPException(status_code=404, detail="Cluster not found.")
    return {"message": "Cluster known fix updated successfully."}

@app.get("/admin/dashboard/knowledge-drafts")
def get_knowledge_drafts(
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db_context)
):
    from app.database.models.workflow_models import KnowledgeDraft
    drafts = db.query(KnowledgeDraft).order_by(KnowledgeDraft.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "problem": d.problem,
            "environment": d.environment,
            "symptoms": d.symptoms,
            "root_cause": d.root_cause,
            "resolution": d.resolution,
            "workaround": d.workaround,
            "tags": d.tags,
            "category": d.category,
            "affected_systems": d.affected_systems,
            "confidence": d.confidence,
            "status": d.status,
            "source_ticket_id": d.source_ticket_id,
            "created_at": d.created_at
        }
        for d in drafts
    ]

@app.get("/tickets/check-duplicate")
def check_duplicate_tickets(
    description: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    return WorkflowService.check_duplicate(db=db, description=description)

@app.post("/tickets/confirm-duplicate")
def confirm_duplicate_ticket(
    body: DuplicateLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    try:
        WorkflowService.confirm_duplicate(db=db, source_id=body.source_ticket_id, target_id=body.target_ticket_id)
        db.commit()
        return {"message": "Duplicate relationship confirmed and tickets linked."}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tickets/dismiss-duplicate")
def dismiss_duplicate_ticket(
    body: DuplicateLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services.workflow_service import WorkflowService
    try:
        WorkflowService.dismiss_duplicate(db=db, source_id=body.source_ticket_id, target_id=body.target_ticket_id)
        db.commit()
        return {"message": "Duplicate relationship warning dismissed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Base Admin Portal Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/admin/knowledge/articles")
def admin_list_articles(
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    return kas.list_all_articles()

@app.get("/api/admin/knowledge/articles/{article_id}")
def admin_get_article(
    article_id: str,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    art = kas.get_article(article_id)
    if not art:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found")
    return art

@app.post("/api/admin/knowledge/articles")
def admin_create_article(
    body: dict,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    try:
        return kas.create_article(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/admin/knowledge/articles/{article_id}")
def admin_update_article(
    article_id: str,
    body: dict,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    try:
        return kas.update_article(article_id, body)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/knowledge/articles/{article_id}")
def admin_delete_article(
    article_id: str,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    try:
        kas.delete_article(article_id)
        return {"message": "Article deleted successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/knowledge/articles/{article_id}/publish")
def admin_publish_article(
    article_id: str,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    try:
        return kas.publish_article(article_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/knowledge/articles/{article_id}/archive")
def admin_archive_article(
    article_id: str,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    try:
        return kas.archive_article(article_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/knowledge/articles/{article_id}/versions")
def admin_get_versions(
    article_id: str,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    return kas.get_version_history(article_id)

@app.get("/api/admin/knowledge/articles/{article_id}/versions/{version}")
def admin_get_version_content(
    article_id: str,
    version: str,
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    content = kas.get_version_content(article_id, version)
    if not content:
        raise HTTPException(status_code=404, detail=f"Version {version} of {article_id} not found")
    return content

@app.post("/api/admin/knowledge/articles/{article_id}/upload")
def admin_upload_screenshot(
    article_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    import app.services.knowledge_admin_service as kas
    try:
        content = file.file.read()
        saved_filename = kas.upload_screenshot(article_id, file.filename, content)
        return {"filename": saved_filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# ITSM Workflow Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/itsm/manager-approvals")
def get_manager_approval_queue(
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db_context)
):
    """Returns all SERVICE_REQUEST and PRIVILEGED_ACTION tickets pending manager approval."""
    logger.info("ITSM: GET /api/itsm/manager-approvals for user %s", current_user.username)
    if current_user.role not in ("MANAGER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Only Managers and Admins can view the approval queue.")

    from app.database.models.ticket import Ticket
    tickets_q = db.query(Ticket).filter(
        (
            (Ticket.request_type.in_(["SERVICE_REQUEST", "PRIVILEGED_ACTION"])) |
            (Ticket.status.in_(["WAITING_MANAGER_APPROVAL", "WAITING_MANAGER"]))
        ),
        Ticket.approval_status == "PENDING",
        Ticket.status.notin_(["REJECTED", "CLOSED"])
    )

    # Managers can only see tickets assigned to them or unassigned
    if current_user.role == "MANAGER":
        tickets_q = tickets_q.filter(
            (Ticket.manager == current_user.username) | (Ticket.manager == None)
        )

    results = []
    for t in tickets_q.order_by(Ticket.created_at.desc()).all():
        results.append({
            "ticket_id": t.ticket_id,
            "category": t.category,
            "description": t.description or t.issue_description,
            "issue_description": t.issue_description,
            "assigned_team": t.assigned_team,
            "priority": t.priority,
            "status": t.status,
            "created_by": t.created_by,
            "created_at": t.created_at.isoformat() + "Z",
            "updated_at": t.updated_at.isoformat() + "Z" if t.updated_at else t.created_at.isoformat() + "Z",
            "request_type": t.request_type,
            "manager": t.manager,
            "approval_status": t.approval_status,
            "assignment_group": t.assignment_group or t.assigned_team,
            "sla_hours": t.sla_hours,
            "sla_state": t.sla_state or "HEALTHY",
        })
    return {"count": len(results), "tickets": results}


@app.get("/api/itsm/admin-queue")
def get_admin_queue(
    status: str | None = None,
    request_type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Returns all tickets in the admin processing queue (non-closed, non-rejected)."""
    logger.info("ITSM: GET /api/itsm/admin-queue for user %s", current_user.username)
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only Admins can view the full admin queue.")

    from app.database.models.ticket import Ticket
    tickets_q = db.query(Ticket).filter(
        Ticket.status.notin_(["CLOSED", "REJECTED"])
    )

    if status:
        tickets_q = tickets_q.filter(Ticket.status == status.upper())
    if request_type:
        tickets_q = tickets_q.filter(Ticket.request_type == request_type.upper())

    results = []
    for t in tickets_q.order_by(Ticket.created_at.desc()).all():
        results.append({
            "ticket_id": t.ticket_id,
            "category": t.category,
            "description": t.description or t.issue_description,
            "issue_description": t.issue_description,
            "assigned_team": t.assigned_team,
            "assigned_engineer": t.assigned_engineer,
            "priority": t.priority,
            "status": t.status,
            "created_by": t.created_by,
            "created_at": t.created_at.isoformat() + "Z",
            "updated_at": t.updated_at.isoformat() + "Z" if t.updated_at else t.created_at.isoformat() + "Z",
            "resolved_at": t.resolved_at.isoformat() + "Z" if t.resolved_at else None,
            "request_type": t.request_type,
            "manager": t.manager,
            "approval_status": t.approval_status,
            "assignment_group": t.assignment_group or t.assigned_team,
            "sla_hours": t.sla_hours,
            "sla_state": t.sla_state or "HEALTHY",
            "sla_breached": t.sla_breached or False,
        })
    return {"count": len(results), "tickets": results}


@app.get("/api/itsm/my-requests")
def get_my_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Returns tickets created by the current user with full ITSM metadata for status tracking."""
    from app.database.models.ticket import Ticket
    tickets_q = db.query(Ticket).filter(Ticket.created_by == current_user.username)
    results = []
    for t in tickets_q.order_by(Ticket.created_at.desc()).all():
        results.append({
            "ticket_id": t.ticket_id,
            "category": t.category,
            "description": t.description or t.issue_description,
            "issue_description": t.issue_description,
            "assigned_team": t.assigned_team,
            "assigned_engineer": t.assigned_engineer,
            "priority": t.priority,
            "status": t.status,
            "created_by": t.created_by,
            "created_at": t.created_at.isoformat() + "Z",
            "updated_at": t.updated_at.isoformat() + "Z" if t.updated_at else t.created_at.isoformat() + "Z",
            "resolved_at": t.resolved_at.isoformat() + "Z" if t.resolved_at else None,
            "closed_at": t.closed_at.isoformat() + "Z" if t.closed_at else None,
            "request_type": t.request_type,
            "manager": t.manager,
            "approval_status": t.approval_status,
            "assignment_group": t.assignment_group or t.assigned_team,
            "sla_hours": t.sla_hours,
            "sla_state": t.sla_state or "HEALTHY",
            "sla_breached": t.sla_breached or False,
        })
    return {"count": len(results), "tickets": results}


@app.get("/api/itsm/manager-tickets")
def get_manager_tickets(
    approval_status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Returns tickets for manager view, filtered by approval_status."""
    if current_user.role not in ("MANAGER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Only Managers and Admins can view manager tickets.")

    import datetime
    from app.database.models.ticket import Ticket
    from app.database.models.audit_log import AuditLog
    from app.database.models.agent_trace import AgentTrace

    query = db.query(Ticket).filter(
        (
            (Ticket.request_type.in_(["SERVICE_REQUEST", "PRIVILEGED_ACTION"])) |
            (Ticket.status.in_(["WAITING_MANAGER_APPROVAL", "WAITING_MANAGER", "READY_FOR_ADMIN", "ACCESS_GRANTED", "COMPLETED", "APPROVED", "REJECTED"])) |
            (Ticket.approval_status.in_(["PENDING", "APPROVED", "REJECTED"]))
        )
    )

    if current_user.role == "MANAGER":
        query = query.filter(
            (Ticket.manager == current_user.username) | (Ticket.manager == None)
        )

    if approval_status and approval_status.upper() != "ALL":
        query = query.filter(Ticket.approval_status == approval_status.upper())

    results = []
    for t in query.order_by(Ticket.created_at.desc()).all():
        # Get AI Diagnosis / Recommendation dynamically
        audit_record = db.query(AuditLog).filter(AuditLog.ticket_id == t.ticket_id).first()
        session_id = audit_record.session_id if audit_record else None
        
        ai_recommendation = None
        if session_id:
            trace = db.query(AgentTrace).filter(AgentTrace.session_id == session_id).first()
            if trace and trace.output_data:
                out_data = trace.output_data
                if isinstance(out_data, dict):
                    ai_recommendation = out_data.get("summary") or out_data.get("thought")
        
        if not ai_recommendation:
            # Fallback based on category
            if t.category == "VPN":
                ai_recommendation = "Verify AD lock status and reset remote access gateway session."
            elif t.category == "Password":
                ai_recommendation = "Check domain controller lockout status and unlock AD user."
            elif t.category == "Software":
                ai_recommendation = "Approve license assignment for Microsoft Visio."
            else:
                ai_recommendation = f"Verify request alignment with {t.category} policies."

        # Extract software requested name cleanly
        software_req = t.category
        desc_low = (t.description or t.issue_description or "").lower()
        if "sap" in desc_low:
            software_req = "SAP GUI"
        elif "adobe" in desc_low:
            software_req = "Adobe Acrobat"
        elif "visio" in desc_low:
            software_req = "Microsoft Visio"
        elif "teams" in desc_low:
            software_req = "Microsoft Teams"
        elif "citrix" in desc_low:
            software_req = "Citrix Workspace"

        approved_by_val = getattr(t, "approved_by", None) or t.manager or ("manager" if t.approval_status == "APPROVED" else None)
        approved_at_val = t.approved_at.isoformat() + "Z" if getattr(t, "approved_at", None) else (t.updated_at.isoformat() + "Z" if (t.approval_status in ("APPROVED", "REJECTED") and t.updated_at) else None)
        approval_notes_val = getattr(t, "approval_notes", None) or ("Approved via Manager Portal." if t.approval_status == "APPROVED" else None)

        laps_active_val = getattr(t, "laps_active", False) or (t.status == "ACCESS_GRANTED")
        laps_exp_iso = t.laps_expiration.isoformat() + "Z" if getattr(t, "laps_expiration", None) else None

        results.append({
            "ticket_id": t.ticket_id,
            "category": t.category,
            "description": t.description or t.issue_description,
            "issue_description": t.issue_description,
            "assigned_team": t.assigned_team,
            "assigned_engineer": t.assigned_engineer,
            "priority": t.priority,
            "status": t.status,
            "created_by": t.created_by,
            "created_at": t.created_at.isoformat() + "Z",
            "updated_at": t.updated_at.isoformat() + "Z" if t.updated_at else t.created_at.isoformat() + "Z",
            "resolved_at": t.resolved_at.isoformat() + "Z" if t.resolved_at else None,
            "closed_at": t.closed_at.isoformat() + "Z" if t.closed_at else None,
            "request_type": t.request_type,
            "manager": t.manager,
            "approval_status": t.approval_status,
            "approved_by": approved_by_val,
            "approved_at": approved_at_val,
            "approval_notes": approval_notes_val,
            "software_requested": software_req,
            "assignment_group": t.assignment_group or t.assigned_team,
            "sla_hours": t.sla_hours,
            "sla_state": t.sla_state or "HEALTHY",
            "sla_breached": t.sla_breached or False,
            "ai_recommendation": ai_recommendation,
            "laps_active": laps_active_val,
            "laps_password": getattr(t, "laps_password", None),
            "laps_expiration": laps_exp_iso,
            "temp_admin_credentials": {
                "username": ".\\Administrator",
                "password": getattr(t, "laps_password", "Temp@4821#"),
                "status": "EXPIRED" if (isinstance(getattr(t, "laps_expiration", None), datetime.datetime) and datetime.datetime.utcnow() > t.laps_expiration) else ("ACTIVE" if laps_active_val else "PENDING"),
                "valid_for_minutes": 15,
                "expires_at": laps_exp_iso,
                "source": "Mock Enterprise Integration"
            } if laps_active_val else None
        })
    return {"count": len(results), "tickets": results}


@app.post("/api/itsm/manager-tickets/{ticket_id}/approve")
def approve_manager_ticket(
    ticket_id: str,
    request: dict = Body(default={}),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    if current_user.role not in ("MANAGER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Only Managers and Admins can approve tickets.")
    
    from app.database.models.ticket import Ticket
    from app.services.timeline_service import TimelineService
    from app.services.rbac_audit_service import log_rbac_event
    
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
        
    import datetime
    old_status = ticket.status
    
    # Phase 6.3: Approve transitions ticket to READY_FOR_ADMIN so Admin Queue shows the action button.
    ticket.status = "READY_FOR_ADMIN"
    ticket.approval_status = "APPROVED"
    ticket.approved_by = current_user.username
    ticket.approved_at = datetime.datetime.utcnow()
    note_val = request.get("notes") or request.get("reason") or "Approved via Manager Portal."
    ticket.approval_notes = note_val
    db.commit()

    # Log Admin approval requested
    try:
        from app.database.models.session import SessionModel
        from app.core.logging_context import session_id_ctx
        from app.services.observability_service import log_event
        session_record = db.query(SessionModel).filter(SessionModel.active_ticket == ticket_id).first()
        if session_record:
            session_id_ctx.set(session_record.session_id)
            log_event(
                "Admin approval requested",
                db=db,
                category=ticket.category,
                ticket_id=ticket_id
            )
    except Exception as _obs_err:
        logger.warning("Failed to log admin approval requested: %s", _obs_err)
    
    try:
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="MANAGER_APPROVED",
            actor=current_user.username,
            action="manager_approve",
            description=f"Request approved by manager {current_user.username}. Reason: {request.get('reason', 'Approved via Manager Portal.')}"
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=ticket.status,
            details={"action": "manager_approve", "reason": request.get('reason', '')}
        )
        db.commit()
    except Exception as _audit_err:
        logger.warning("manager_approve: audit/timeline write failed (non-critical, ticket already approved): %s", _audit_err)
        try:
            db.rollback()
        except Exception:
            pass
    return {"message": "Ticket request successfully approved.", "status": ticket.status}


@app.post("/api/itsm/manager-tickets/{ticket_id}/reject")
def reject_manager_ticket(
    ticket_id: str,
    request: dict = Body(default={}),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    if current_user.role not in ("MANAGER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Only Managers and Admins can reject tickets.")
        
    from app.database.models.ticket import Ticket
    from app.services.timeline_service import TimelineService
    from app.services.rbac_audit_service import log_rbac_event
    
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
        
    import datetime
    old_status = ticket.status
    ticket.status = "REJECTED"
    ticket.approval_status = "REJECTED"
    ticket.approved_by = current_user.username
    ticket.approved_at = datetime.datetime.utcnow()
    ticket.approval_notes = request.get("reason") or request.get("notes") or "Rejected by manager."
    db.commit()
    
    try:
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="MANAGER_REJECTED",
            actor=current_user.username,
            action="manager_reject",
            description=f"Request rejected by manager {current_user.username}. Reason: {request.get('reason', 'Rejected via Manager Portal.')}"
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state="REJECTED",
            details={"action": "manager_reject", "reason": request.get('reason', '')}
        )
        db.commit()
    except Exception as _audit_err:
        logger.warning("manager_reject: audit/timeline write failed (non-critical, ticket already rejected): %s", _audit_err)
        try:
            db.rollback()
        except Exception:
            pass
    return {"message": "Ticket request rejected successfully.", "status": "REJECTED"}


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6.3: Admin Queue — Grant Temporary Admin Access (Mock) & Complete Installation
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/itsm/admin-queue/{ticket_id}/grant-admin-access")
def grant_admin_access(
    ticket_id: str,
    request: dict = Body(default={}),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """
    Phase 6.3: Mock admin access grant step.
    Transitions ticket from READY_FOR_ADMIN → ACCESS_GRANTED.

    TODO: Replace with real enterprise integration:
      - CyberArk API  (Privileged Access Management)
      - Windows LAPS  (Local Administrator Password Solution)
      - Azure PIM     (Privileged Identity Management)
    """
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only Admins can grant temporary admin access.")

    from app.database.models.ticket import Ticket
    from app.services.timeline_service import TimelineService
    from app.services.rbac_audit_service import log_rbac_event
    from app.services.notification_service import create_notification as _notif

    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if ticket.status not in ("READY_FOR_ADMIN", "WAITING_ADMIN", "WAITING_ADMIN_APPROVAL", "APPROVED"):
        raise HTTPException(
            status_code=400,
            detail=f"Ticket must be in READY_FOR_ADMIN status to grant access. Current status: {ticket.status}"
        )

    import datetime
    old_status = ticket.status
    ticket.status = "ACCESS_GRANTED"
    ticket.laps_active = True
    ticket.laps_password = "Temp@4821#"
    now_utc = datetime.datetime.utcnow()
    expires_dt = now_utc + datetime.timedelta(minutes=15)
    ticket.laps_expiration = expires_dt
    ticket.laps_audit_id = f"LAPS-{int(now_utc.timestamp())}"
    db.commit()

    try:
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="ADMIN_ACCESS_GRANTED",
            actor=current_user.username,
            action="grant_admin_access",
            description=(
                f"Temporary administrator access granted by {current_user.username}. "
                "(Mock Enterprise Integration) — "
                "TODO: Replace with CyberArk API / Windows LAPS / Azure PIM"
            )
        )
        _notif(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Temporary administrator access has been granted for your request {ticket_id}. Installation can now proceed."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state="ACCESS_GRANTED",
            details={"action": "grant_admin_access", "mock": True}
        )
        db.commit()
    except Exception as _audit_err:
        logger.warning("grant_admin_access: audit write failed (non-critical): %s", _audit_err)
        try:
            db.rollback()
        except Exception:
            pass

    return {
        "message": "Temporary administrator access granted (Mock Enterprise Integration)",
        "status": "ACCESS_GRANTED",
        "mock": True,
        "note": "TODO: Replace with CyberArk API / Windows LAPS / Azure PIM",
        "temp_admin_credentials": {
            "username": ".\\Administrator",
            "password": "Temp@4821#",
            "status": "ACTIVE",
            "valid_for_minutes": 15,
            "expires_at": expires_dt.isoformat() + "Z",
            "source": "Mock Enterprise Integration"
        }
    }


@app.post("/api/itsm/admin-queue/{ticket_id}/complete-installation")
def complete_installation(
    ticket_id: str,
    request: dict = Body(default={}),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Phase 6.3: Marks the privileged action as completed after admin has granted access."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only Admins can complete installations.")

    from app.database.models.ticket import Ticket
    from app.services.timeline_service import TimelineService
    from app.services.rbac_audit_service import log_rbac_event
    from app.services.notification_service import create_notification as _notif

    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if ticket.status not in ("ACCESS_GRANTED", "TEMP_ADMIN_GRANTED"):
        raise HTTPException(
            status_code=400,
            detail=f"Ticket must be in ACCESS_GRANTED status to complete. Current: {ticket.status}"
        )

    old_status = ticket.status
    ticket.status = "COMPLETED"
    db.commit()

    try:
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="INSTALLATION_COMPLETED",
            actor=current_user.username,
            action="complete_installation",
            description=f"Installation/privileged action completed by admin {current_user.username}."
        )
        _notif(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Your request {ticket_id} has been completed. The installation was successful."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state="COMPLETED",
            details={"action": "complete_installation"}
        )
        db.commit()
    except Exception as _audit_err:
        logger.warning("complete_installation: audit write failed (non-critical): %s", _audit_err)
        try:
            db.rollback()
        except Exception:
            pass

    return {
        "message": "Installation completed successfully.",
        "status": "COMPLETED"
    }


@app.get("/system/provider")
def get_active_provider(
    current_user: User = Depends(RoleChecker(["ADMIN", "MANAGER"]))
):
    from app.services.ai_provider import get_ai_provider
    provider = get_ai_provider()
    return {
        "provider": provider.__class__.__name__.replace("Provider", "").lower(),
        "model": getattr(provider, "_model_name", "unknown"),
        "ready": provider.is_ready()
    }


# ── Sprint 5 Admin Endpoints ─────────────────────────────────────────────────

@app.get("/api/itsm/users")
def get_itsm_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Returns system users for Admin Portal Users view."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only Administrators can view users.")
    
    users = db.query(User).order_by(User.username.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() + "Z" if u.created_at else None
        }
        for u in users
    ]

@app.get("/api/itsm/assignment-groups")
def get_itsm_assignment_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Returns assignment groups and assigned workload metrics."""
    if current_user.role not in ("ADMIN", "MANAGER"):
        raise HTTPException(status_code=403, detail="Only Managers and Admins can view assignment groups.")
    
    groups = [
        {"name": "Helpdesk", "manager": "mgr_sarah", "engineers": ["Emily Watson (Helpdesk L2)", "John Helpdesk", "Sarah L1"]},
        {"name": "Network", "manager": "mgr_sarah", "engineers": ["Alex Net", "Dave Router"]},
        {"name": "Security", "manager": "admin_alex", "engineers": ["Security Officer", "Elena Sec"]},
        {"name": "Hardware", "manager": "mgr_sarah", "engineers": ["Hardware Tech", "Marcus Repair"]},
        {"name": "Database", "manager": "admin_alex", "engineers": ["DBA Lead", "Sql Master"]},
        {"name": "Access Management", "manager": "admin_alex", "engineers": ["IAM Admin", "Access Specialist"]},
        {"name": "Cloud Infrastructure", "manager": "admin_alex", "engineers": ["Cloud Ops", "Aws DevOps"]}
    ]
    
    from app.database.models.ticket import Ticket
    open_tickets = db.query(Ticket).filter(Ticket.status.notin_(["RESOLVED", "CLOSED", "REJECTED"])).all()
    group_counts = {}
    for t in open_tickets:
        grp = t.assignment_group or t.assigned_team or "Helpdesk"
        group_counts[grp] = group_counts.get(grp, 0) + 1

    for g in groups:
        g["open_tickets_count"] = group_counts.get(g["name"], 0)
        g["engineer_count"] = len(g["engineers"])

    return {"assignment_groups": groups}

@app.delete("/tickets/{ticket_id}")
def delete_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Allows Admin to delete a ticket."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only Administrators can delete tickets.")
    
    from app.database.models.ticket import Ticket
    from app.services.rbac_audit_service import log_rbac_event

    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")
    
    log_rbac_event(
        user=current_user.username,
        role=current_user.role,
        action="delete_ticket",
        ticket_id=ticket_id,
        old_state=ticket.status,
        new_state="DELETED",
        details={"deleted_by": current_user.username}
    )
    
    db.delete(ticket)
    db.commit()
    logger.info("Admin %s deleted ticket %s", current_user.username, ticket_id)
    return {"message": f"Ticket '{ticket_id}' has been permanently deleted.", "ticket_id": ticket_id}

@app.post("/tickets/{ticket_id}/update")
def update_ticket_details(
    ticket_id: str,
    updates: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    """Allows Admin to update ticket fields."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only Administrators can update full ticket details.")
    
    from app.database.models.ticket import Ticket
    from app.services.rbac_audit_service import log_rbac_event
    import datetime

    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")

    old_state = ticket.status
    if "category" in updates and updates["category"]:
        ticket.category = str(updates["category"])
    if "priority" in updates and updates["priority"]:
        ticket.priority = str(updates["priority"]).upper()
    if "status" in updates and updates["status"]:
        ticket.status = str(updates["status"]).upper()
    if "assigned_team" in updates and updates["assigned_team"]:
        ticket.assigned_team = str(updates["assigned_team"])
        ticket.assignment_group = str(updates["assigned_team"])
    if "assigned_engineer" in updates and updates["assigned_engineer"]:
        ticket.assigned_engineer = str(updates["assigned_engineer"])
    if "issue_description" in updates and updates["issue_description"]:
        ticket.issue_description = str(updates["issue_description"])
    
    ticket.updated_at = datetime.datetime.utcnow()
    db.commit()

    log_rbac_event(
        user=current_user.username,
        role=current_user.role,
        action="update_ticket_details",
        ticket_id=ticket_id,
        old_state=old_state,
        new_state=ticket.status,
        details=updates
    )
    db.commit()
    logger.info("Admin %s updated ticket %s: %s", current_user.username, ticket_id, updates)
    return {"message": "Ticket updated successfully", "ticket_id": ticket_id}


# ── Sprint 6 Analytics & SLA Endpoints ────────────────────────────────────────

@app.get("/analytics/overview")
@app.get("/api/analytics/overview")
def api_get_analytics_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services import analytics_service
    return analytics_service.get_overview_metrics(db)

@app.get("/analytics/tickets")
@app.get("/api/analytics/tickets")
def api_get_analytics_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services import analytics_service
    return analytics_service.get_ticket_metrics(db)

@app.get("/analytics/sla")
@app.get("/api/analytics/sla")
def api_get_analytics_sla(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services import analytics_service
    return analytics_service.get_sla_metrics(db)

@app.get("/analytics/approvals")
@app.get("/api/analytics/approvals")
def api_get_analytics_approvals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services import analytics_service
    return analytics_service.get_approval_metrics(db)

@app.get("/analytics/assignment-groups")
@app.get("/api/analytics/assignment-groups")
def api_get_analytics_assignment_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services import analytics_service
    return analytics_service.get_assignment_group_metrics(db)

@app.get("/analytics/users")
@app.get("/api/analytics/users")
def api_get_analytics_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    from app.services import analytics_service
    return analytics_service.get_user_metrics(db)


# ── Sprint 7: Knowledge Management Portal REST API ────────────────────────────
# Wires existing knowledge_admin_service.py to HTTP endpoints.
# Admin routes: full CRUD, version history, publish, unpublish, archive, restore, upload, import, export
# Public routes: search & read only for published articles

import json as _json
import datetime as _datetime

from app.services import knowledge_admin_service as _kb_admin
import app.services.knowledge_service as _ks


class KnowledgeArticleRequest(BaseModel):
    title: str = ""
    category: str = "VPN"
    source: str = "Bridgestone IT Knowledge Base"
    status: str = "draft"
    keywords: list = []
    problem: str = ""
    symptoms: list = []
    prerequisites: list = []
    troubleshooting_steps: list = []
    verification: list = []
    common_errors: list = []
    escalation: dict = {}
    screenshots: list = []
    faq: list = []
    related_articles: list = []


# --- Admin endpoints ---

@app.get("/api/admin/knowledge/articles")
def kb_list_articles(
    status: str = None,
    category: str = None,
    q: str = None,
    current_user: User = Depends(get_current_user)
):
    """List all knowledge articles (admin: includes drafts/archived)."""
    articles = _kb_admin.list_all_articles()
    if status and status != "ALL":
        articles = [a for a in articles if a.get("status", "draft").lower() == status.lower()]
    if category and category != "ALL":
        articles = [a for a in articles if a.get("category", "").upper() == category.upper()]
    if q:
        q_lower = q.lower()
        articles = [
            a for a in articles
            if q_lower in a.get("title", "").lower()
            or q_lower in a.get("problem", "").lower()
            or any(q_lower in str(k).lower() for k in a.get("keywords", []))
            or any(q_lower in str(s).lower() for s in a.get("symptoms", []))
            or q_lower in a.get("category", "").lower()
        ]
    return articles


@app.get("/api/admin/knowledge/articles/{article_id}",
         openapi_extra={"x-order": 2})
def kb_get_article(article_id: str, current_user: User = Depends(get_current_user)):
    """Get a single article by ID (admin). Note: 'export' is handled before this route."""
    # Guard: route conflict protection — 'export' is a reserved path
    if article_id == "export":
        articles = _kb_admin.list_all_articles()
        export_payload = {
            "export_version": "1.0",
            "exported_at": _datetime.datetime.utcnow().isoformat() + "Z",
            "exported_by": current_user.username,
            "article_count": len(articles),
            "articles": articles
        }
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=export_payload,
            headers={"Content-Disposition": "attachment; filename=bridgestone_kb_export.json"}
        )
    art = _kb_admin.get_article(article_id)
    if not art:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found.")
    return art


@app.post("/api/admin/knowledge/articles")
def kb_create_article(payload: KnowledgeArticleRequest, current_user: User = Depends(get_current_user)):
    """Create a new draft article."""
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Only Admins can create knowledge articles.")
    try:
        new_article = _kb_admin.create_article(payload.model_dump())
        return new_article
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/admin/knowledge/articles/{article_id}")
def kb_update_article(article_id: str, payload: KnowledgeArticleRequest, current_user: User = Depends(get_current_user)):
    """Update an existing article."""
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Only Admins can edit knowledge articles.")
    try:
        updated = _kb_admin.update_article(article_id, payload.model_dump())
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/admin/knowledge/articles/{article_id}")
def kb_delete_article(article_id: str, current_user: User = Depends(get_current_user)):
    """Delete an article permanently."""
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Only Admins can delete knowledge articles.")
    try:
        _kb_admin.delete_article(article_id)
        return {"message": f"Article {article_id} deleted successfully."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/admin/knowledge/articles/{article_id}/publish")
def kb_publish_article(article_id: str, current_user: User = Depends(get_current_user)):
    """Publish a draft article. Creates a version snapshot and increments version number."""
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Only Admins can publish knowledge articles.")
    try:
        updated = _kb_admin.publish_article(article_id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/admin/knowledge/articles/{article_id}/unpublish")
def kb_unpublish_article(article_id: str, current_user: User = Depends(get_current_user)):
    """Revert a published article back to draft."""
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Only Admins can unpublish knowledge articles.")
    art = _kb_admin.get_article(article_id)
    if not art:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found.")
    updated = _kb_admin.update_article(article_id, {"status": "draft"})
    _ks.load_articles()
    return updated


@app.post("/api/admin/knowledge/articles/{article_id}/archive")
def kb_archive_article(article_id: str, current_user: User = Depends(get_current_user)):
    """Archive an article (excluded from AI retrieval)."""
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Only Admins can archive knowledge articles.")
    try:
        updated = _kb_admin.archive_article(article_id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/admin/knowledge/articles/{article_id}/restore")
def kb_restore_article(article_id: str, current_user: User = Depends(get_current_user)):
    """Restore an archived article back to draft."""
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Only Admins can restore knowledge articles.")
    art = _kb_admin.get_article(article_id)
    if not art:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found.")
    updated = _kb_admin.update_article(article_id, {"status": "draft"})
    _ks.load_articles()
    return updated


@app.get("/api/admin/knowledge/articles/{article_id}/versions")
def kb_get_versions(article_id: str, current_user: User = Depends(get_current_user)):
    """Get the version history for an article."""
    return _kb_admin.get_version_history(article_id)


@app.get("/api/admin/knowledge/articles/{article_id}/versions/{version}")
def kb_get_version_content(article_id: str, version: str, current_user: User = Depends(get_current_user)):
    """Get the content of a specific historical version."""
    content = _kb_admin.get_version_content(article_id, version)
    if not content:
        raise HTTPException(status_code=404, detail=f"Version {version} for article {article_id} not found.")
    return content


@app.post("/api/admin/knowledge/articles/{article_id}/upload")
async def kb_upload_screenshot(
    article_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload a screenshot image for a knowledge article step."""
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Only Admins can upload images.")
    try:
        content = await file.read()
        safe_filename = _kb_admin.upload_screenshot(article_id, file.filename or "upload.png", content)
        return {"filename": safe_filename, "message": "Image uploaded successfully."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/knowledge/import")
async def kb_import_articles(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Import articles from a JSON bundle. Validates schema before import."""
    if current_user.role not in ("ADMIN",):
        raise HTTPException(status_code=403, detail="Only Admins can import knowledge articles.")
    try:
        raw = await file.read()
        payload = _json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file. Could not parse upload.")

    # Accept either an array or a bundle with an 'articles' key
    articles_raw = payload if isinstance(payload, list) else payload.get("articles", [])
    if not isinstance(articles_raw, list):
        raise HTTPException(status_code=400, detail="JSON must be an array of articles or a bundle with 'articles' key.")

    REQUIRED = {"title", "category", "keywords", "problem", "symptoms", "troubleshooting_steps", "verification", "escalation", "screenshots", "faq"}
    created = []
    errors = []
    for idx, art in enumerate(articles_raw):
        missing = REQUIRED - set(art.keys())
        if missing:
            errors.append({"index": idx, "error": f"Missing required fields: {', '.join(sorted(missing))}"})
            continue
        try:
            new_art = _kb_admin.create_article(art)
            created.append(new_art.get("article_id"))
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})

    return {
        "imported": len(created),
        "skipped": len(errors),
        "created_ids": created,
        "errors": errors
    }


# --- Public (authenticated) read routes ---

@app.get("/knowledge/articles")
def kb_public_list(q: str = None, category: str = None, current_user: User = Depends(get_current_user)):
    """Return published articles only (used by employees and search)."""
    articles = [a for a in _kb_admin.list_all_articles() if a.get("status") == "published"]
    if category and category != "ALL":
        articles = [a for a in articles if a.get("category", "").upper() == category.upper()]
    if q:
        q_lower = q.lower()
        articles = [
            a for a in articles
            if q_lower in a.get("title", "").lower()
            or q_lower in a.get("problem", "").lower()
            or any(q_lower in str(k).lower() for k in a.get("keywords", []))
            or any(q_lower in str(s).lower() for s in a.get("symptoms", []))
        ]
    return articles


@app.get("/knowledge/articles/{article_id}")
def kb_public_get(article_id: str, current_user: User = Depends(get_current_user)):
    """Return a single published article."""
    art = _kb_admin.get_article(article_id)
    if not art:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found.")
    if art.get("status") != "published":
        raise HTTPException(status_code=403, detail="This article is not published.")
    return art


@app.get("/knowledge/search")
def kb_public_search(q: str = "", category: str = None, current_user: User = Depends(get_current_user)):
    """Full-text search across published knowledge articles."""
    return kb_public_list(q=q, category=category, current_user=current_user)




