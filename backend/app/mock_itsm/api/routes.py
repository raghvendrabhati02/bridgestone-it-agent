"""
routes.py
─────────────────────────────────────────────────────────────────────────────
REST API routes for Mock ITSM Platform operations (Sprint 2 & Sprint 3).
Includes Ticket Management and Approval Workflows.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.mock_itsm.database import get_mock_itsm_db
from app.mock_itsm.schemas.mock_itsm_schemas import (
    MockTicketCreateRequest,
    MockTicketUpdateRequest,
    MockTicketResponse,
    MockApprovalRequest,
    MockApprovalActionRequest,
    MockApprovalResponse,
    MockNotificationResponse,
    MockAssignmentGroupResponse,
    MockAuditLogResponse,
)
from app.mock_itsm.services.mock_incident_service import MockIncidentService
from app.mock_itsm.services.mock_approval_service import MockApprovalService
from app.mock_itsm.services.mock_notification_service import MockNotificationService
from app.mock_itsm.services.mock_audit_service import MockAuditService
from app.mock_itsm.repositories.mock_itsm_repository import MockITSMRepository

router = APIRouter(tags=["Mock ITSM Platform"])


# ── Sprint 2: Ticket Management Endpoints ────────────────────────────────────

@router.post("/mock-itsm/incidents", response_model=MockTicketResponse)
@router.post("/api/mock-itsm/tickets", response_model=MockTicketResponse)
def create_incident(payload: MockTicketCreateRequest, db: Session = Depends(get_mock_itsm_db)):
    svc = MockIncidentService(db)
    ticket = svc.create_incident(**payload.dict())
    return ticket


@router.get("/mock-itsm/incidents", response_model=List[MockTicketResponse])
@router.get("/api/mock-itsm/tickets", response_model=List[MockTicketResponse])
def list_incidents(
    status: Optional[str] = None,
    assigned_group: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_mock_itsm_db)
):
    svc = MockIncidentService(db)
    return svc.list_incidents(status=status, assigned_group=assigned_group, category=category, search_query=search, limit=limit)


@router.get("/mock-itsm/incidents/{ticket_number}", response_model=MockTicketResponse)
@router.get("/api/mock-itsm/tickets/{ticket_number}", response_model=MockTicketResponse)
def get_incident(ticket_number: str, db: Session = Depends(get_mock_itsm_db)):
    svc = MockIncidentService(db)
    ticket = svc.get_incident(ticket_number)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Incident {ticket_number} not found.")
    return ticket


@router.put("/mock-itsm/incidents/{ticket_number}", response_model=MockTicketResponse)
@router.patch("/api/mock-itsm/tickets/{ticket_number}", response_model=MockTicketResponse)
def update_incident(ticket_number: str, payload: MockTicketUpdateRequest, db: Session = Depends(get_mock_itsm_db)):
    svc = MockIncidentService(db)
    try:
        updated = svc.update_incident(ticket_number=ticket_number, **payload.dict(exclude_unset=True))
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/mock-itsm/incidents/{ticket_number}/status", response_model=MockTicketResponse)
def update_incident_status(ticket_number: str, status: str = Body(..., embed=True), changed_by: str = Body(default="system", embed=True), reason: Optional[str] = Body(default=None, embed=True), db: Session = Depends(get_mock_itsm_db)):
    svc = MockIncidentService(db)
    try:
        updated = svc.update_incident(ticket_number=ticket_number, status=status, changed_by=changed_by, reason=reason)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/mock-itsm/incidents/{ticket_number}/history")
@router.get("/api/mock-itsm/tickets/{ticket_number}/history")
def get_incident_history(ticket_number: str, db: Session = Depends(get_mock_itsm_db)):
    repo = MockITSMRepository(db)
    history = repo.get_history(ticket_number)
    return [
        {
            "id": h.id,
            "ticket_number": h.ticket_number,
            "changed_by": h.changed_by,
            "field_changed": h.field_changed,
            "old_value": h.old_value,
            "new_value": h.new_value,
            "change_reason": h.change_reason,
            "created_at": h.created_at.isoformat() + "Z"
        }
        for h in history
    ]


@router.delete("/mock-itsm/incidents/{ticket_number}")
def delete_incident(ticket_number: str, db: Session = Depends(get_mock_itsm_db)):
    svc = MockIncidentService(db)
    deleted = svc.delete_incident(ticket_number)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Incident {ticket_number} not found.")
    return {"success": True, "message": f"Incident {ticket_number} deleted."}


# ── Sprint 3: Approval Workflow API Endpoints ───────────────────────────────

@router.post("/mock-itsm/approvals", response_model=MockApprovalResponse)
@router.post("/api/mock-itsm/approvals", response_model=MockApprovalResponse)
def request_approval(
    payload: MockApprovalRequest,
    requester: str = Query(default="employee"),
    db: Session = Depends(get_mock_itsm_db)
):
    svc = MockApprovalService(db)
    try:
        res = svc.request_approval(
            ticket_number=payload.ticket_number,
            requester=requester,
            approver=payload.approver,
            approver_role=payload.approver_role,
            approval_type=payload.approval_type,
            comments=payload.comments,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/mock-itsm/approvals/{approval_id}/action")
@router.post("/api/mock-itsm/approvals/{approval_id}/action")
def action_approval(
    approval_id: int,
    payload: MockApprovalActionRequest,
    approver: str = Query(default="manager"),
    db: Session = Depends(get_mock_itsm_db)
):
    svc = MockApprovalService(db)
    try:
        return svc.action_approval(
            approval_id=approval_id,
            approver_username=approver,
            decision=payload.decision,
            comments=payload.comments
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/mock-itsm/approvals/pending", response_model=List[MockApprovalResponse])
@router.get("/api/mock-itsm/approvals/pending", response_model=List[MockApprovalResponse])
def view_pending_approvals(approver: Optional[str] = Query(default=None), db: Session = Depends(get_mock_itsm_db)):
    svc = MockApprovalService(db)
    return svc.get_pending_approvals(approver_username=approver)


@router.get("/mock-itsm/approvals/my-requests", response_model=List[MockApprovalResponse])
@router.get("/api/mock-itsm/approvals/my-requests", response_model=List[MockApprovalResponse])
def view_my_requests(requester: str = Query(default="employee"), db: Session = Depends(get_mock_itsm_db)):
    svc = MockApprovalService(db)
    return svc.get_my_requests(requester_username=requester)


@router.get("/mock-itsm/approvals", response_model=List[MockApprovalResponse])
@router.get("/api/mock-itsm/approvals", response_model=List[MockApprovalResponse])
def view_all_approvals(db: Session = Depends(get_mock_itsm_db)):
    svc = MockApprovalService(db)
    return svc.get_all_approvals()


@router.get("/mock-itsm/approvals/{approval_id}", response_model=MockApprovalResponse)
@router.get("/api/mock-itsm/approvals/{approval_id}", response_model=MockApprovalResponse)
def get_approval_by_id(approval_id: int, viewer: str = Query(default="system"), db: Session = Depends(get_mock_itsm_db)):
    svc = MockApprovalService(db)
    try:
        return svc.get_approval_by_id(approval_id, viewer=viewer)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/mock-itsm/approvals/{approval_id}/approve", response_model=MockApprovalResponse)
def approve_request(
    approval_id: int,
    approver: str = Query(default="manager"),
    comments: Optional[str] = Body(default=None, embed=True),
    db: Session = Depends(get_mock_itsm_db)
):
    svc = MockApprovalService(db)
    try:
        return svc.action_approval(approval_id=approval_id, approver_username=approver, decision="APPROVED", comments=comments)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mock-itsm/approvals/{approval_id}/reject", response_model=MockApprovalResponse)
def reject_request(
    approval_id: int,
    approver: str = Query(default="manager"),
    comments: Optional[str] = Body(default=None, embed=True),
    db: Session = Depends(get_mock_itsm_db)
):
    svc = MockApprovalService(db)
    try:
        return svc.action_approval(approval_id=approval_id, approver_username=approver, decision="REJECTED", comments=comments)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/mock-itsm/users/{user_id}/approvals", response_model=List[MockApprovalResponse])
def get_user_approvals(user_id: str, db: Session = Depends(get_mock_itsm_db)):
    svc = MockApprovalService(db)
    return svc.get_my_requests(requester_username=user_id)


@router.get("/mock-itsm/approvals/ticket/{ticket_number}", response_model=List[MockApprovalResponse])
@router.get("/api/mock-itsm/approvals/ticket/{ticket_number}", response_model=List[MockApprovalResponse])
def get_ticket_approvals(ticket_number: str, db: Session = Depends(get_mock_itsm_db)):
    svc = MockApprovalService(db)
    return svc.get_ticket_approvals(ticket_number)


# ── Internal Operations ───────────────────────────────────────────────────────

@router.get("/api/mock-itsm/notifications", response_model=List[MockNotificationResponse])
def get_notifications(recipient: Optional[str] = None, db: Session = Depends(get_mock_itsm_db)):
    repo = MockITSMRepository(db)
    return repo.list_notifications(recipient=recipient)


@router.get("/api/mock-itsm/assignment-groups", response_model=List[MockAssignmentGroupResponse])
def list_assignment_groups(db: Session = Depends(get_mock_itsm_db)):
    repo = MockITSMRepository(db)
    return repo.list_assignment_groups()


@router.get("/api/mock-itsm/audit-logs", response_model=List[MockAuditLogResponse])
def list_audit_logs(ticket_number: Optional[str] = None, db: Session = Depends(get_mock_itsm_db)):
    svc = MockAuditService(db)
    return svc.get_audit_trail(ticket_number=ticket_number)
