import datetime
import logging
import json
from app.database.session import get_db
from app.database.repositories.catalog_repository import CatalogRepository
from app.database.repositories.request_repository import RequestRepository
from app.services.notification_service import create_notification
from app.adapters.servicenow_adapter import ServiceNowAdapter
from app.database.models.rbac_audit_log import RbacAuditLog
from app.database.models.approval_history import ApprovalHistory

logger = logging.getLogger("it-agent-backend")
servicenow_client = ServiceNowAdapter()

request_counter = 0

def init_request_counter():
    global request_counter
    try:
        with get_db() as db:
            repo = RequestRepository(db)
            all_reqs = repo.get_all_requests()
            max_num = 0
            for r in all_reqs:
                try:
                    num = int(r.request_id[3:])
                    if num > max_num:
                        max_num = num
                except Exception:
                    pass
            request_counter = max_num
            logger.info("Catalog Service: Initialized request counter to %d from DB", request_counter)
    except Exception as e:
        logger.warning("Catalog Service: Failed to initialize request counter: %s", e)

# Run initialization
init_request_counter()

def get_service_catalog() -> list[dict]:
    with get_db() as db:
        repo = CatalogRepository(db)
        items = repo.get_all_items()
        return [
            {
                "id": i.id,
                "service_id": i.service_id,
                "name": i.name,
                "category": i.category,
                "description": i.description,
                "business_owner": i.business_owner,
                "fulfillment_team": i.fulfillment_team,
                "approval_required": i.approval_required,
                "sla_hours": i.sla_hours,
                "estimated_completion": i.estimated_completion,
                "icon": i.icon,
                "status": i.status
            }
            for i in items
        ]

def get_service_requests(username: str = None, role: str = None) -> list[dict]:
    with get_db() as db:
        repo = RequestRepository(db)
        if role in ["ADMIN", "MANAGER"]:
            reqs = repo.get_all_requests()
        elif username:
            reqs = repo.get_requests_by_user(username)
        else:
            reqs = repo.get_all_requests()
            
        return [
            {
                "id": r.id,
                "request_id": r.request_id,
                "servicenow_id": r.servicenow_id,
                "service_id": r.service_id,
                "service_name": r.service_name,
                "requested_by": r.requested_by,
                "category": r.category,
                "description": r.description,
                "status": r.status,
                "stage": r.stage,
                "assigned_team": r.assigned_team,
                "estimated_completion": r.estimated_completion,
                "sla_hours": r.sla_hours,
                "details": r.details,
                "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
                "updated_at": r.updated_at.isoformat() + "Z" if r.updated_at else None
            }
            for r in reqs
        ]

def get_service_request_details(request_id: str) -> dict | None:
    with get_db() as db:
        repo = RequestRepository(db)
        r = repo.get_request(request_id)
        if not r:
            return None
            
        # Get the audit trail timeline
        audit_logs = db.query(RbacAuditLog).filter(RbacAuditLog.ticket_id == request_id).order_by(RbacAuditLog.timestamp.asc()).all()
        timeline = [
            {
                "timestamp": a.timestamp.isoformat() + "Z",
                "user": a.user,
                "role": a.role,
                "action": a.action,
                "old_state": a.old_state,
                "new_state": a.new_state,
                "details": a.details
            }
            for a in audit_logs
        ]
        
        # Check approval status
        approval = db.query(ApprovalHistory).filter(ApprovalHistory.session_id == request_id).first()
        approval_status = approval.approval_status if approval else None
        
        return {
            "request_id": r.request_id,
            "servicenow_id": r.servicenow_id,
            "service_id": r.service_id,
            "service_name": r.service_name,
            "requested_by": r.requested_by,
            "category": r.category,
            "description": r.description,
            "status": r.status,
            "stage": r.stage,
            "assigned_team": r.assigned_team,
            "estimated_completion": r.estimated_completion,
            "sla_hours": r.sla_hours,
            "details": r.details,
            "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
            "updated_at": r.updated_at.isoformat() + "Z" if r.updated_at else None,
            "timeline": timeline,
            "approval_status": approval_status
        }

def create_service_request(service_id: str, requested_by: str, details_dict: dict) -> dict:
    global request_counter
    request_counter += 1
    request_id = f"REQ{request_counter:07d}"
    
    with get_db() as db:
        catalog_repo = CatalogRepository(db)
        request_repo = RequestRepository(db)
        
        item = catalog_repo.get_item(service_id)
        if not item:
            raise ValueError(f"Service catalog item {service_id} not found")
            
        try:
            snow_incident = servicenow_client.create_incident(
                category=item.category,
                description=f"Service Request for {item.name}: {details_dict.get('Justification', 'No justification provided')}",
                assignment_group=item.fulfillment_team or "Helpdesk"
            )
            servicenow_id = snow_incident.get("sys_id", "REQ" + str(1000000 + request_counter))
        except Exception:
            servicenow_id = "REQ" + str(1000000 + request_counter)
            
        status = "SUBMITTED"
        stage = "Request Submitted"
        
        if item.approval_required:
            status = "PENDING_APPROVAL"
            stage = "Pending Approval"
            
        req_details = json.dumps(details_dict)
        
        req = request_repo.create_request(
            request_id=request_id,
            servicenow_id=servicenow_id,
            service_id=service_id,
            service_name=item.name,
            requested_by=requested_by,
            category=item.category,
            description=f"Request for {item.name}",
            status=status,
            stage=stage,
            assigned_team=item.fulfillment_team,
            estimated_completion=item.estimated_completion,
            sla_hours=item.sla_hours,
            details=req_details
        )
        
        # Audit Logs
        db.add(RbacAuditLog(
            timestamp=req.created_at,
            user=requested_by,
            role="EMPLOYEE",
            action="create_service_request",
            ticket_id=request_id,
            new_state="NEW",
            details=f"Service Request {request_id} created by user."
        ))
        
        db.add(RbacAuditLog(
            timestamp=req.created_at,
            user=requested_by,
            role="EMPLOYEE",
            action="submit_service_request",
            ticket_id=request_id,
            old_state="NEW",
            new_state=status,
            details=f"Service Request details submitted by requester."
        ))
        
        if item.approval_required:
            db.add(ApprovalHistory(
                session_id=request_id,
                recommended_action=f"Approve Service Request: {item.name} for {requested_by}",
                approval_status="PENDING",
                created_at=req.created_at
            ))
            create_notification(
                ticket_id=request_id,
                recipient="manager@bridgestone.com",
                message=f"Approval required for {item.name} request ({request_id}) from {requested_by}."
            )
        else:
            create_notification(
                ticket_id=request_id,
                recipient=item.fulfillment_team or "Helpdesk",
                message=f"New Service Request {request_id} received for {item.name}."
            )
            create_notification(
                ticket_id=request_id,
                recipient=requested_by,
                message=f"Your Service Request {request_id} has been submitted successfully."
            )
            
        db.commit()
        
        return {
            "request_id": req.request_id,
            "servicenow_id": req.servicenow_id,
            "service_id": req.service_id,
            "service_name": req.service_name,
            "requested_by": req.requested_by,
            "status": req.status,
            "stage": req.stage,
            "assigned_team": req.assigned_team,
            "sla_hours": req.sla_hours
        }

def perform_request_action(request_id: str, action: str, user: str, role: str, note: str = None) -> dict | None:
    with get_db() as db:
        repo = RequestRepository(db)
        r = repo.get_request(request_id)
        if not r:
            return None
            
        old_status = r.status
        old_stage = r.stage
        new_status = old_status
        new_stage = old_stage
        
        now = datetime.datetime.utcnow()
        
        if action == "approve":
            if role not in ["MANAGER", "ADMIN"]:
                raise PermissionError("Only managers or admins can approve requests")
            if old_status != "PENDING_APPROVAL":
                raise ValueError("Request is not pending approval")
            new_status = "APPROVED"
            new_stage = "Awaiting Fulfillment"
            
            app = db.query(ApprovalHistory).filter(ApprovalHistory.session_id == request_id).first()
            if app:
                app.approval_status = "APPROVED"
                
            db.add(RbacAuditLog(
                timestamp=now,
                user=user,
                role=role,
                action="approve_service_request",
                ticket_id=request_id,
                old_state=old_status,
                new_state=new_status,
                details=f"Service request approved. {f'Note: {note}' if note else ''}"
            ))
            
            create_notification(
                ticket_id=request_id,
                recipient=r.assigned_team or "Helpdesk",
                message=f"Request {request_id} approved. Please begin fulfillment."
            )
            create_notification(
                ticket_id=request_id,
                recipient=r.requested_by,
                message=f"Your request {request_id} has been approved."
            )
            
        elif action == "reject":
            if role not in ["MANAGER", "ADMIN"]:
                raise PermissionError("Only managers or admins can reject requests")
            if old_status != "PENDING_APPROVAL":
                raise ValueError("Request is not pending approval")
            new_status = "REJECTED"
            new_stage = "Request Rejected"
            
            app = db.query(ApprovalHistory).filter(ApprovalHistory.session_id == request_id).first()
            if app:
                app.approval_status = "REJECTED"
                
            db.add(RbacAuditLog(
                timestamp=now,
                user=user,
                role=role,
                action="reject_service_request",
                ticket_id=request_id,
                old_state=old_status,
                new_state=new_status,
                details=f"Service request rejected. Reason: {note or 'Not specified'}"
            ))
            
            create_notification(
                ticket_id=request_id,
                recipient=r.requested_by,
                message=f"Your request {request_id} has been rejected: {note or 'No reason provided'}"
            )
            
        elif action == "start_fulfillment":
            if role != "ADMIN":
                raise PermissionError("Only administrators can perform fulfillment tasks")
            if old_status not in ["APPROVED", "SUBMITTED"]:
                raise ValueError("Request must be approved or submitted to start fulfillment")
            new_status = "FULFILLMENT"
            new_stage = "Fulfillment in Progress"
            
            db.add(RbacAuditLog(
                timestamp=now,
                user=user,
                role=role,
                action="start_fulfillment",
                ticket_id=request_id,
                old_state=old_status,
                new_state=new_status,
                details=f"Fulfillment started. {f'Note: {note}' if note else ''}"
            ))
            
            create_notification(
                ticket_id=request_id,
                recipient=r.requested_by,
                message=f"Fulfillment for your request {request_id} has started."
            )
            
        elif action == "complete":
            if role != "ADMIN":
                raise PermissionError("Only administrators can mark requests as completed")
            if old_status != "FULFILLMENT":
                raise ValueError("Request must be in fulfillment to complete")
            new_status = "COMPLETED"
            new_stage = "Request Completed"
            
            db.add(RbacAuditLog(
                timestamp=now,
                user=user,
                role=role,
                action="complete_service_request",
                ticket_id=request_id,
                old_state=old_status,
                new_state=new_status,
                details=f"Fulfillment completed. {f'Note: {note}' if note else ''}"
            ))
            
            create_notification(
                ticket_id=request_id,
                recipient=r.requested_by,
                message=f"Your request {request_id} is completed."
            )
            
        elif action == "close":
            if old_status != "COMPLETED" and role != "ADMIN":
                raise ValueError("Only completed requests can be closed, unless you are an admin")
            new_status = "CLOSED"
            new_stage = "Request Closed"
            
            db.add(RbacAuditLog(
                timestamp=now,
                user=user,
                role=role,
                action="close_service_request",
                ticket_id=request_id,
                old_state=old_status,
                new_state=new_status,
                details=f"Service request closed. {f'Note: {note}' if note else ''}"
            ))
            
            create_notification(
                ticket_id=request_id,
                recipient=r.requested_by,
                message=f"Your request {request_id} has been closed."
            )
            
        elif action == "add_note":
            db.add(RbacAuditLog(
                timestamp=now,
                user=user,
                role=role,
                action="add_note",
                ticket_id=request_id,
                old_state=old_status,
                new_state=old_status,
                details=f"Work Note added: {note or ''}"
            ))
            
        else:
            raise ValueError(f"Unknown action {action}")
            
        r.status = new_status
        r.stage = new_stage
        r.updated_at = now
        db.commit()
        db.refresh(r)
        
        return get_service_request_details(request_id)
