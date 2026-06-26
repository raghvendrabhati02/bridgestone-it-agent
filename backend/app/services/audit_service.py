import datetime
import logging
from app.database.session import get_db
from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.action_repository import ActionRepository
from app.database.repositories.approval_repository import ApprovalRepository
from app.database.repositories.trace_repository import TraceRepository

logger = logging.getLogger("it-agent-backend")

def log_audit(session_id: str, user_message: str, category: str, decision: str, approval_status: str, recommended_action: str, action_result: dict, ticket_id: str, servicenow_id: str):
    """
    Logs an audit record of important events/turns in the database.
    """
    try:
        with get_db() as db:
            repo = AuditRepository(db)
            log = repo.save(
                session_id=session_id,
                user_message=user_message,
                category=category,
                decision=decision,
                approval_status=approval_status,
                recommended_action=recommended_action,
                action_result=action_result,
                ticket_id=ticket_id,
                servicenow_id=servicenow_id
            )
            logger.info("Audit Service: Logged audit record for session %s to database", session_id)
            return {
                "timestamp": log.created_at.isoformat() + "Z",
                "session_id": log.session_id,
                "user_message": log.user_message,
                "category": log.category,
                "decision": log.decision,
                "approval_status": log.approval_status,
                "recommended_action": log.recommended_action,
                "action_result": log.action_result,
                "ticket_id": log.ticket_id,
                "servicenow_id": log.servicenow_id
            }
    except Exception as e:
        logger.error("Audit Service: Failed to save audit log: %s", e)
        # Volatile fallback for resilience
        return {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "user_message": user_message,
            "category": category,
            "decision": decision,
            "approval_status": approval_status,
            "recommended_action": recommended_action,
            "action_result": action_result,
            "ticket_id": ticket_id,
            "servicenow_id": servicenow_id
        }

def get_all_audit_logs() -> list:
    try:
        with get_db() as db:
            repo = AuditRepository(db)
            logs = repo.get_all()
            return [
                {
                    "timestamp": log.created_at.isoformat() + "Z",
                    "session_id": log.session_id,
                    "user_message": log.user_message,
                    "category": log.category,
                    "decision": log.decision,
                    "approval_status": log.approval_status,
                    "recommended_action": log.recommended_action,
                    "action_result": log.action_result,
                    "ticket_id": log.ticket_id,
                    "servicenow_id": log.servicenow_id
                }
                for log in logs
            ]
    except Exception as e:
        logger.error("Audit Service: Failed to get audit logs: %s", e)
        return []

def log_action(request_id: str, action_type: str, status: str, approved_by_user: bool, servicenow_id: str = None) -> dict:
    """
    Logs Action Agent executions in the action_history table.
    """
    try:
        from app.core.metrics import BUSINESS_ACTIONS_EXECUTED_TOTAL
        BUSINESS_ACTIONS_EXECUTED_TOTAL.inc()
    except Exception:
        pass
    try:
        with get_db() as db:
            repo = ActionRepository(db)
            action = repo.save(
                request_id=request_id,
                action_type=action_type,
                status=status,
                approved_by_user=approved_by_user,
                servicenow_id=servicenow_id
            )
            record = {
                "request_id": action.request_id,
                "action_type": action.action_type,
                "status": action.status,
                "created_at": action.created_at.isoformat() + "Z",
                "approved_by_user": action.approved_by_user,
                "servicenow_id": action.servicenow_id
            }
    except Exception as e:
        logger.error("Audit Service: Failed to save action log: %s", e)
        record = {
            "request_id": request_id,
            "action_type": action_type,
            "status": status,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "approved_by_user": approved_by_user,
            "servicenow_id": servicenow_id
        }
        
    # Also sync with the list in action_service.py for backward compatibility
    try:
        from app.services.action_service import actions
        if not any(a.get("request_id") == request_id for a in actions):
            actions.append(record)
    except Exception as e:
        logger.warning("Audit Service: Could not sync action with action_service actions: %s", e)
        
    logger.info("Audit Service: Logged action %s (Request: %s)", action_type, request_id)
    return record

def get_all_actions_history() -> list:
    try:
        with get_db() as db:
            repo = ActionRepository(db)
            actions_list = repo.get_all()
            return [
                {
                    "request_id": action.request_id,
                    "action_type": action.action_type,
                    "status": action.status,
                    "created_at": action.created_at.isoformat() + "Z",
                    "approved_by_user": action.approved_by_user,
                    "servicenow_id": action.servicenow_id
                }
                for action in actions_list
            ]
    except Exception as e:
        logger.error("Audit Service: Failed to get actions history: %s", e)
        return []

def log_approval(session_id: str, recommended_action: str, approval_status: str) -> dict:
    """
    Logs recommended action approvals/rejections/pendings.
    """
    try:
        from app.core.metrics import BUSINESS_APPROVALS_TOTAL
        status_map = {
            "PENDING": "requested",
            "APPROVED": "approved",
            "REJECTED": "rejected",
            "ACCESS_DENIED": "denied"
        }
        mapped_status = status_map.get(approval_status.upper().strip(), "requested")
        BUSINESS_APPROVALS_TOTAL.labels(status=mapped_status).inc()
    except Exception:
        pass
    try:
        with get_db() as db:
            repo = ApprovalRepository(db)
            approval = repo.save(
                session_id=session_id,
                recommended_action=recommended_action,
                approval_status=approval_status
            )
            logger.info("Audit Service: Logged approval state %s for session %s to database", approval_status, session_id)
            return {
                "session_id": approval.session_id,
                "recommended_action": approval.recommended_action,
                "approval_status": approval.approval_status,
                "timestamp": approval.created_at.isoformat() + "Z"
            }
    except Exception as e:
        logger.error("Audit Service: Failed to save approval log: %s", e)
        return {
            "session_id": session_id,
            "recommended_action": recommended_action,
            "approval_status": approval_status,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }

def get_all_approvals_history() -> list:
    try:
        with get_db() as db:
            repo = ApprovalRepository(db)
            approvals = repo.get_all()
            return [
                {
                    "session_id": approval.session_id,
                    "recommended_action": approval.recommended_action,
                    "approval_status": approval.approval_status,
                    "timestamp": approval.created_at.isoformat() + "Z"
                }
                for approval in approvals
            ]
    except Exception as e:
        logger.error("Audit Service: Failed to get approvals history: %s", e)
        return []

def log_agent_trace(session_id: str, agent_name: str, output: dict) -> dict:
    """
    Logs agent intermediate trace logs.
    """
    try:
        with get_db() as db:
            repo = TraceRepository(db)
            trace = repo.save(
                session_id=session_id,
                agent_name=agent_name,
                output_data=output
            )
            logger.info("Audit Service: Logged trace for agent '%s' under session %s to database", agent_name, session_id)
            return {
                "session_id": trace.session_id,
                "agent_name": trace.agent_name,
                "output": trace.output_data,
                "correlation_id": trace.correlation_id,
                "timestamp": trace.created_at.isoformat() + "Z"
            }
    except Exception as e:
        logger.error("Audit Service: Failed to save agent trace: %s", e)
        from app.core.logging_context import correlation_id_ctx
        return {
            "session_id": session_id,
            "agent_name": agent_name,
            "output": output,
            "correlation_id": correlation_id_ctx.get() or "",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }

def get_all_agent_traces() -> list:
    try:
        with get_db() as db:
            repo = TraceRepository(db)
            traces = repo.get_all()
            return [
                {
                    "session_id": trace.session_id,
                    "agent_name": trace.agent_name,
                    "output": trace.output_data,
                    "correlation_id": trace.correlation_id,
                    "timestamp": trace.created_at.isoformat() + "Z"
                }
                for trace in traces
            ]
    except Exception as e:
        logger.error("Audit Service: Failed to get agent traces: %s", e)
        return []
