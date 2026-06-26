import logging
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.intent_service import detect_intent
from app.services.conversation_service import (
    start_conversation,
    process_message,
    handle_chat_turn
)
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

app = FastAPI(
    title="Bridgestone IT Agent",
    version="1.0.0"
)

# Enable CORS Middleware to allow requests from the Next.js frontend (e.g., http://localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify the exact origins permitted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import time
from fastapi import Request
from fastapi.responses import Response

SESSION_CORRELATION_CACHE = {}

def get_correlation_id_for_session(session_id: str) -> str:
    if not session_id:
        return ""
    if session_id in SESSION_CORRELATION_CACHE:
        return SESSION_CORRELATION_CACHE[session_id]
    try:
        from app.database.connection import SessionLocal
        db = SessionLocal()
        from app.database.models.agent_trace import AgentTrace
        trace = db.query(AgentTrace).filter(AgentTrace.session_id == session_id).filter(AgentTrace.correlation_id != None).first()
        if trace:
            SESSION_CORRELATION_CACHE[session_id] = trace.correlation_id
            db.close()
            return trace.correlation_id
        from app.database.models.audit_log import AuditLog
        log = db.query(AuditLog).filter(AuditLog.session_id == session_id).filter(AuditLog.correlation_id != None).first()
        if log:
            SESSION_CORRELATION_CACHE[session_id] = log.correlation_id
            db.close()
            return log.correlation_id
        db.close()
    except Exception:
        pass
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
    
    # Exclude /metrics, /system-status, /health from polluting metrics
    if path in ("/metrics", "/system-status", "/health"):
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
                db_sess.close()
        except Exception:
            pass
            
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
        
    start_time = time.time()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
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
        
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={"detail": err_msg, "error_code": exc_name}
    )

@app.get("/metrics")
def get_metrics():
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/system-status")
def system_status(db: Session = Depends(get_db_context)):
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

# Include Auth Router
app.include_router(auth_router)
app.include_router(analytics_router)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

class TicketCreateRequest(BaseModel):
    category: str
    issue_description: str

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

    # 3. Gemini LLM API check
    gemini_status = "unhealthy"
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            # If initialization is fine and API key is present
            gemini_status = "healthy"
        except Exception as e:
            logger.error("Health Check: Gemini configuration failed: %s", e)
    else:
        gemini_status = "unconfigured (missing API key)"

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
def chat(request: ChatRequest, current_user: User = Depends(get_current_user)):
    logger.info("FastAPI Endpoint POST '/chat': Received request from user %s with payload: %s", current_user.username, request.model_dump_json())
    response_payload = handle_chat_turn(request.session_id, request.message, username=current_user.username, user_role=current_user.role)
    logger.info("FastAPI Endpoint POST '/chat': Returning response payload: %s", response_payload)
    return response_payload


@app.get("/tickets")
def list_tickets(current_user: User = Depends(get_current_user)):
    logger.info("FastAPI Endpoint GET '/tickets': Fetching tickets for user %s", current_user.username)
    all_tickets = get_all_tickets()
    if current_user.role in ("ADMIN", "MANAGER"):
        return all_tickets
    else:
        # Filter tickets created by this employee
        return [t for t in all_tickets if t.get("created_by") == current_user.username]

@app.post("/ticket")
def make_ticket(request: TicketCreateRequest, current_user: User = Depends(get_current_user)):
    logger.info("FastAPI Endpoint POST '/ticket': Creating manual ticket for category=%s, user=%s", request.category, current_user.username)
    return create_ticket(request.category, request.issue_description, created_by=current_user.username)


class TicketActionRequest(BaseModel):
    action: str
    team: str | None = None
    priority: str | None = None
    note: str | None = None


@app.post("/tickets/{ticket_id}/action")
def run_ticket_action(
    ticket_id: str,
    request: TicketActionRequest,
    current_user: User = Depends(RoleChecker(["ADMIN"])),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint POST '/tickets/%s/action': Action=%s, user=%s", ticket_id, request.action, current_user.username)
    from app.database.models.ticket import Ticket
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
    
    if action == "add_note":
        if not request.note:
            raise HTTPException(status_code=400, detail="Note content is required for action 'add_note'.")
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="add_internal_note",
            ticket_id=ticket_id,
            details={"note": request.note}
        )
        return {"message": "Internal note added successfully."}

    # Otherwise we are updating fields
    new_status = old_status
    new_priority = old_priority
    new_team = old_team

    if action in ("assign_team", "transfer_team"):
        if not request.team:
            raise HTTPException(status_code=400, detail="Team name is required for assignment actions.")
        new_team = request.team
        new_status = "ASSIGNED"
        ticket.assigned_team = new_team
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
            details={"action": request.action, "assigned_team": new_team, "note": request.note or ""}
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

    elif action == "request_more_information":
        new_status = "WAITING_FOR_USER"
        ticket.status = new_status
        db.commit()

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
        new_status = "RESOLVED"
        ticket.status = new_status
        db.commit()

        create_notification(
            ticket_id=ticket_id,
            recipient=ticket.created_by or "Employee",
            message=f"Ticket {ticket_id} has been marked as RESOLVED."
        )
        log_rbac_event(
            user=current_user.username,
            role=current_user.role,
            action="update_ticket_lifecycle",
            ticket_id=ticket_id,
            old_state=old_status,
            new_state=new_status,
            details={"action": "resolve", "note": request.note or ""}
        )

    elif action == "close":
        new_status = "CLOSED"
        ticket.status = new_status
        db.commit()

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

    else:
        raise HTTPException(status_code=400, detail=f"Action '{request.action}' not recognized.")

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
                "note": request.note or f"Admin action: {action}"
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
            "name": "Raghvendra Bhati",
            "department": "IT Service Desk Operations",
            "location": "Bangalore, India",
            "email": "employee@bridgestone.com",
            "role": "EMPLOYEE"
        },
        "manager": {
            "name": "Sarah Jenkins",
            "department": "IT Service Desk Management",
            "location": "Tokyo, Japan",
            "email": "manager@bridgestone.com",
            "role": "MANAGER"
        },
        "admin": {
            "name": "Alex Rivera",
            "department": "IT Infrastructure & Security",
            "location": "Nashville, USA",
            "email": "admin@bridgestone.com",
            "role": "ADMIN"
        }
    }
    
    if creator_username in PROFILES:
        req_profile = PROFILES[creator_username]
    elif creator_user:
        req_profile = {
            "name": creator_username.title(),
            "department": "Operations",
            "location": "Bridgestone HQ",
            "email": creator_user.email,
            "role": creator_user.role
        }
    else:
        req_profile = {
            "name": creator_username.title(),
            "department": "Operations",
            "location": "Bridgestone HQ",
            "email": f"{creator_username}@bridgestone.com",
            "role": "EMPLOYEE"
        }

    # 4. Assignment Information
    assigned_team = ticket.assigned_team or "Helpdesk"
    engineers = {
        "Network": "Robert Chen (NetOps)",
        "Helpdesk": "Emily Watson (Helpdesk L2)",
        "Sysadmin": "Marcus Aurelius (SysOps)",
        "Security": "Vesper Lynd (SecOps)",
        "Hardware": "Dave Grohl (Hardware Desk)",
        "General": "IT Generalist Queue Manager"
    }
    assigned_engineer = engineers.get(assigned_team, "Emily Watson (Helpdesk L2)")
    
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

    # Sort timeline events chronologically
    timeline.sort(key=lambda x: x["timestamp"])

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
    
    if not ai_diagnosis:
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
        ai_diagnosis = fallback_diag.get(ticket.category, {
            "summary": f"Incident logged in category {ticket.category}. AI initialized basic diagnostic trace.",
            "root_cause": "Undetermined software or hardware incident.",
            "troubleshooting_steps": "1. Logged ticket details.\n2. Assigned to support queue.",
            "tools_executed": ["create_ticket"],
            "confidence_score": 85
        })

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
            "sla_state": ticket.sla_state or "HEALTHY",
            "sla_breached": ticket.sla_breached or False,
            "sla_breached_at": ticket.sla_breached_at.isoformat() + "Z" if ticket.sla_breached_at else None
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
        "timeline": timeline,
        "conversation": chat_history,
        "ai_diagnosis": ai_diagnosis,
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
def list_notifications(current_user: User = Depends(get_current_user)):
    logger.info("FastAPI Endpoint GET '/notifications': Fetching notifications for user %s", current_user.username)
    all_notifs = get_notifications()
    if current_user.role in ("ADMIN", "MANAGER"):
        return all_notifs
    else:
        # Filter notifications for this employee
        return [n for n in all_notifs if n.get("recipient") in ("Employee", current_user.username)]

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
    from app.core.json_logger import setup_json_logging
    setup_json_logging(logging.INFO)
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
