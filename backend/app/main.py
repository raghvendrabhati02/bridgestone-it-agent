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

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    from app.core.metrics import HTTP_REQUESTS_TOTAL, HTTP_FAILURES_TOTAL, HTTP_REQUEST_DURATION_SECONDS
    method = request.method
    path = request.url.path
    
    # Exclude /metrics, /system-status, /health from polluting metrics
    if path in ("/metrics", "/system-status", "/health"):
        return await call_next(request)
        
    try:
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path).inc()
    except Exception:
        pass
        
    start_time = time.time()
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        try:
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
            if response.status_code >= 400:
                HTTP_FAILURES_TOTAL.labels(method=method, path=path, status_code=str(response.status_code)).inc()
        except Exception:
            pass
        return response
    except Exception as e:
        duration = time.time() - start_time
        try:
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
            HTTP_FAILURES_TOTAL.labels(method=method, path=path, status_code="500").inc()
        except Exception:
            pass
        raise e

@app.get("/metrics")
def get_metrics():
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/system-status")
def system_status(db: Session = Depends(get_db_context)):
    logger.info("FastAPI Endpoint GET '/system-status': Status checked")
    return health(db)

# Include Auth Router
app.include_router(auth_router)


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

    # 5. Overall status determination
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
        "adapters": adapters_status
    }


@app.post("/chat")
def chat(request: ChatRequest, current_user: User = Depends(get_current_user)):
    logger.info("FastAPI Endpoint POST '/chat': Received request from user %s with payload: %s", current_user.username, request.model_dump_json())
    response_payload = handle_chat_turn(request.session_id, request.message, username=current_user.username)
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
