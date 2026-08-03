import datetime
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.database.models.notification import Notification
from app.services.audit_service import log_audit

logger = logging.getLogger("it-agent-backend")

# Volatile fallback list for testing/resilience when DB unavailable
notifications_fallback: List[Dict[str, Any]] = []

def _get_ticket_attr(ticket: Any, attr: str, default: Any = None) -> Any:
    """Helper to extract attribute whether ticket is an object or a dict."""
    if isinstance(ticket, dict):
        return ticket.get(attr, default)
    return getattr(ticket, attr, default)

class NotificationService:
    @staticmethod
    def create_notification(
        user_id: str,
        type: str,
        title: str,
        message: str,
        ticket_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Core notification creation method.
        Persists to database, triggers audit logging, and updates business metrics.
        """
        timestamp = datetime.datetime.utcnow()
        timestamp_iso = timestamp.isoformat() + "Z"
        
        try:
            from app.core.metrics import BUSINESS_NOTIFICATIONS_SENT_TOTAL
            BUSINESS_NOTIFICATIONS_SENT_TOTAL.inc()
        except Exception:
            pass

        def _persist(session: Session) -> Dict[str, Any]:
            notif = Notification(
                user_id=user_id,
                ticket_id=ticket_id,
                type=type,
                title=title,
                message=message,
                is_read=False,
                created_at=timestamp,
                recipient=user_id,
                notification_id=f"NOTIF_{int(timestamp.timestamp() * 1000)}",
                status="SENT"
            )
            session.add(notif)
            session.commit()
            session.refresh(notif)
            
            # Audit log requirement
            try:
                log_audit(
                    session_id=f"NOTIF-{notif.id}",
                    user_message=title,
                    category="NOTIFICATION",
                    decision=type,
                    approval_status="SENT",
                    recommended_action="SEND_NOTIFICATION",
                    action_result={
                        "notification_id": notif.id,
                        "user_id": user_id,
                        "ticket_id": ticket_id,
                        "type": type,
                        "title": title,
                        "message": message
                    },
                    ticket_id=ticket_id or "",
                    servicenow_id=""
                )
            except Exception as audit_err:
                logger.warning("NotificationService: Failed to write audit log for notification %s: %s", notif.id, audit_err)

            logger.info("NotificationService: Created notification %d (%s) for user '%s'", notif.id, type, user_id)
            return {
                "id": notif.id,
                "user_id": notif.user_id,
                "ticket_id": notif.ticket_id,
                "type": notif.type,
                "title": notif.title,
                "message": notif.message,
                "is_read": notif.is_read,
                "created_at": notif.created_at.isoformat() + "Z",
                "read_at": notif.read_at.isoformat() + "Z" if notif.read_at else None,
                "recipient": notif.recipient,
                "status": notif.status
            }

        try:
            if db:
                return _persist(db)
            else:
                with get_db() as session:
                    return _persist(session)
        except Exception as e:
            logger.error("NotificationService: Failed to save notification to DB: %s", e)
            fallback_obj = {
                "id": len(notifications_fallback) + 1,
                "user_id": user_id,
                "ticket_id": ticket_id,
                "type": type,
                "title": title,
                "message": message,
                "is_read": False,
                "created_at": timestamp_iso,
                "read_at": None,
                "recipient": user_id,
                "status": "SENT"
            }
            notifications_fallback.append(fallback_obj)
            return fallback_obj

    @classmethod
    def notify_ticket_created(cls, ticket: Any, user_id: Optional[str] = None, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Triggered when a ticket is created."""
        ticket_id = _get_ticket_attr(ticket, "ticket_id") or _get_ticket_attr(ticket, "id") or "UNKNOWN"
        creator = user_id or _get_ticket_attr(ticket, "created_by") or "employee"
        category = _get_ticket_attr(ticket, "category") or "General"
        manager = _get_ticket_attr(ticket, "manager") or "manager"

        recipients = set([creator, manager, "admin"])
        results = []
        for r in recipients:
            if r:
                notif = cls.create_notification(
                    user_id=str(r),
                    type="TICKET_CREATED",
                    title=f"Ticket Created: {ticket_id}",
                    message=f"Ticket {ticket_id} ({category}) was created successfully.",
                    ticket_id=str(ticket_id),
                    db=db
                )
                results.append(notif)
        return results

    @classmethod
    def notify_assignment(cls, ticket: Any, previous_assignee: Optional[str] = None, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Triggered when a ticket is assigned or assignment changes."""
        ticket_id = _get_ticket_attr(ticket, "ticket_id") or "UNKNOWN"
        engineer = _get_ticket_attr(ticket, "assigned_engineer") or _get_ticket_attr(ticket, "assigned_team") or "IT Support"
        creator = _get_ticket_attr(ticket, "created_by")
        event_type = "ASSIGNMENT_CHANGED" if previous_assignee else "TICKET_ASSIGNED"
        
        title = f"Assignment Changed: {ticket_id}" if previous_assignee else f"Ticket Assigned: {ticket_id}"
        message = f"Ticket {ticket_id} has been assigned to {engineer}."

        recipients = set([engineer, creator, previous_assignee, "admin"])
        results = []
        for r in recipients:
            if r:
                notif = cls.create_notification(
                    user_id=str(r),
                    type=event_type,
                    title=title,
                    message=message,
                    ticket_id=str(ticket_id),
                    db=db
                )
                results.append(notif)
        return results

    @classmethod
    def notify_status_change(cls, ticket: Any, previous_status: Optional[str] = None, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Triggered when ticket status changes."""
        ticket_id = _get_ticket_attr(ticket, "ticket_id") or "UNKNOWN"
        status = _get_ticket_attr(ticket, "status") or "UNKNOWN"
        creator = _get_ticket_attr(ticket, "created_by")
        engineer = _get_ticket_attr(ticket, "assigned_engineer")
        manager = _get_ticket_attr(ticket, "manager")

        event_type = "TICKET_CLOSED" if status == "CLOSED" else "STATUS_CHANGED"
        title = f"Ticket Closed: {ticket_id}" if status == "CLOSED" else f"Status Changed: {ticket_id}"
        prev_str = f" from {previous_status}" if previous_status else ""
        message = f"Ticket {ticket_id} status changed{prev_str} to {status}."

        recipients = set([creator, engineer, manager, "admin"])
        results = []
        for r in recipients:
            if r:
                notif = cls.create_notification(
                    user_id=str(r),
                    type=event_type,
                    title=title,
                    message=message,
                    ticket_id=str(ticket_id),
                    db=db
                )
                results.append(notif)
        return results

    @classmethod
    def notify_approval(
        cls,
        ticket: Any,
        approval_type: str,
        status: str,
        approver: Optional[str] = None,
        requester: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Triggered for approval events: Approval Requested, Approved, Rejected."""
        ticket_id = _get_ticket_attr(ticket, "ticket_id") or "UNKNOWN"
        req_user = requester or _get_ticket_attr(ticket, "created_by") or "employee"
        mgr_user = approver or _get_ticket_attr(ticket, "manager") or "manager"

        status_clean = str(status).upper()
        if status_clean in ("PENDING", "REQUESTED"):
            event_type = "APPROVAL_REQUESTED"
            title = f"Approval Requested for Ticket {ticket_id}"
            message = f"Ticket {ticket_id} ({approval_type}) requires your approval."
            recipients = [mgr_user, "admin"]
        elif status_clean in ("APPROVED", "FULFILLED"):
            event_type = "APPROVAL_APPROVED"
            title = f"Approval Granted for Ticket {ticket_id}"
            message = f"Ticket {ticket_id} ({approval_type}) has been approved by {mgr_user}."
            recipients = [req_user, mgr_user, "admin"]
        else:
            event_type = "APPROVAL_REJECTED"
            title = f"Approval Rejected for Ticket {ticket_id}"
            message = f"Ticket {ticket_id} ({approval_type}) was rejected by {mgr_user}."
            recipients = [req_user, mgr_user, "admin"]

        results = []
        for r in set(recipients):
            if r:
                notif = cls.create_notification(
                    user_id=str(r),
                    type=event_type,
                    title=title,
                    message=message,
                    ticket_id=str(ticket_id),
                    db=db
                )
                results.append(notif)
        return results

    @classmethod
    def notify_resolution(cls, ticket: Any, resolved_by: Optional[str] = None, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Triggered when a ticket is resolved."""
        ticket_id = _get_ticket_attr(ticket, "ticket_id") or "UNKNOWN"
        creator = _get_ticket_attr(ticket, "created_by")
        manager = _get_ticket_attr(ticket, "manager")
        engineer = _get_ticket_attr(ticket, "assigned_engineer")

        title = f"Ticket Resolved: {ticket_id}"
        message = f"Ticket {ticket_id} has been marked as RESOLVED."

        recipients = set([creator, manager, engineer, "admin"])
        results = []
        for r in recipients:
            if r:
                notif = cls.create_notification(
                    user_id=str(r),
                    type="TICKET_RESOLVED",
                    title=title,
                    message=message,
                    ticket_id=str(ticket_id),
                    db=db
                )
                results.append(notif)
        return results

    @classmethod
    def notify_sla(cls, ticket: Any, event_type: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Triggered for SLA Warning or SLA Breach."""
        ticket_id = _get_ticket_attr(ticket, "ticket_id") or "UNKNOWN"
        engineer = _get_ticket_attr(ticket, "assigned_engineer")
        manager = _get_ticket_attr(ticket, "manager")
        creator = _get_ticket_attr(ticket, "created_by")

        norm_type = "SLA_BREACH" if "BREACH" in str(event_type).upper() else "SLA_WARNING"
        title_str = "SLA Breach Alert" if norm_type == "SLA_BREACH" else "SLA Warning Alert"
        title = f"{title_str}: Ticket {ticket_id}"
        message = f"SLA event ({norm_type}) registered for ticket {ticket_id}."

        recipients = set([engineer, manager, creator, "admin"])
        results = []
        for r in recipients:
            if r:
                notif = cls.create_notification(
                    user_id=str(r),
                    type=norm_type,
                    title=title,
                    message=message,
                    ticket_id=str(ticket_id),
                    db=db
                )
                results.append(notif)
        return results

    @classmethod
    def notify_comment_added(
        cls,
        ticket: Any,
        comment_author: str,
        comment_text: str,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Triggered when a comment is added to a ticket."""
        ticket_id = _get_ticket_attr(ticket, "ticket_id") or "UNKNOWN"
        creator = _get_ticket_attr(ticket, "created_by")
        engineer = _get_ticket_attr(ticket, "assigned_engineer")
        manager = _get_ticket_attr(ticket, "manager")

        recipients = set([creator, engineer, manager, "admin"]) - set([comment_author])
        snippet = comment_text[:80] + "..." if len(comment_text) > 80 else comment_text
        title = f"New Comment on {ticket_id}"
        message = f"{comment_author} added a comment: \"{snippet}\""

        results = []
        for r in recipients:
            if r:
                notif = cls.create_notification(
                    user_id=str(r),
                    type="COMMENT_ADDED",
                    title=title,
                    message=message,
                    ticket_id=str(ticket_id),
                    db=db
                )
                results.append(notif)
        return results

    # ── Database Read / Update / Delete Helpers ───────────────────────────────

    @staticmethod
    def get_user_notifications(
        user_id: str,
        user_role: str = "EMPLOYEE",
        unread_only: bool = False,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves notifications for user_id (or role matches) sorted by created_at desc."""
        def _get(session: Session):
            query = session.query(Notification)
            # If user is admin/manager, also match generic recipient strings or user_id
            if user_role.upper() in ("ADMIN", "MANAGER"):
                query = query.filter(
                    (Notification.user_id == user_id) | 
                    (Notification.recipient == user_id) |
                    (Notification.user_id.in_([user_role.lower(), "all"]))
                )
            else:
                query = query.filter(
                    (Notification.user_id == user_id) |
                    (Notification.recipient == user_id) |
                    (Notification.user_id.in_([user_role.lower(), "employee"]))
                )
            
            if unread_only:
                query = query.filter(Notification.is_read == False)
            
            records = query.order_by(desc(Notification.created_at)).all()
            return [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "ticket_id": r.ticket_id,
                    "type": r.type,
                    "title": r.title,
                    "message": r.message,
                    "is_read": bool(r.is_read),
                    "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
                    "read_at": r.read_at.isoformat() + "Z" if r.read_at else None,
                    "recipient": r.recipient or r.user_id,
                    "notification_id": r.notification_id or f"NOTIF_{r.id}",
                    "status": r.status or "SENT"
                }
                for r in records
            ]

        try:
            if db:
                return _get(db)
            else:
                with get_db() as session:
                    return _get(session)
        except Exception as e:
            logger.error("NotificationService: Failed to retrieve user notifications: %s", e)
            res = [
                n for n in notifications_fallback
                if n.get("user_id") in (user_id, user_role.lower()) or n.get("recipient") in (user_id, user_role.lower())
            ]
            if unread_only:
                res = [n for n in res if not n.get("is_read")]
            return sorted(res, key=lambda x: x.get("created_at") or "", reverse=True)

    @staticmethod
    def mark_as_read(notification_id: int, user_id: str, db: Optional[Session] = None) -> bool:
        """Marks a notification as read."""
        now = datetime.datetime.utcnow()
        def _mark(session: Session):
            notif = session.query(Notification).filter(Notification.id == notification_id).first()
            if not notif:
                # Try finding by notification_id string
                notif = session.query(Notification).filter(Notification.notification_id == str(notification_id)).first()
            if notif:
                notif.is_read = True
                notif.read_at = now
                notif.status = "READ"
                session.commit()
                logger.info("NotificationService: Marked notification %s as read", notification_id)
                return True
            return False

        try:
            if db:
                return _mark(db)
            else:
                with get_db() as session:
                    return _mark(session)
        except Exception as e:
            logger.error("NotificationService: Failed to mark notification %s as read: %s", notification_id, e)
            for n in notifications_fallback:
                if str(n.get("id")) == str(notification_id) or n.get("notification_id") == str(notification_id):
                    n["is_read"] = True
                    n["read_at"] = now.isoformat() + "Z"
                    return True
            return False

    @staticmethod
    def mark_all_as_read(user_id: str, user_role: str = "EMPLOYEE", db: Optional[Session] = None) -> int:
        """Marks all notifications for a user as read."""
        now = datetime.datetime.utcnow()
        def _mark_all(session: Session):
            query = session.query(Notification).filter(Notification.is_read == False)
            if user_role.upper() in ("ADMIN", "MANAGER"):
                query = query.filter(
                    (Notification.user_id == user_id) |
                    (Notification.recipient == user_id) |
                    (Notification.user_id.in_([user_role.lower(), "all"]))
                )
            else:
                query = query.filter(
                    (Notification.user_id == user_id) |
                    (Notification.recipient == user_id) |
                    (Notification.user_id.in_([user_role.lower(), "employee"]))
                )
            count = 0
            for notif in query.all():
                notif.is_read = True
                notif.read_at = now
                notif.status = "READ"
                count += 1
            session.commit()
            logger.info("NotificationService: Marked %d notifications as read for user '%s'", count, user_id)
            return count

        try:
            if db:
                return _mark_all(db)
            else:
                with get_db() as session:
                    return _mark_all(session)
        except Exception as e:
            logger.error("NotificationService: Failed to mark all notifications as read: %s", e)
            c = 0
            for n in notifications_fallback:
                if (n.get("user_id") in (user_id, user_role.lower()) or n.get("recipient") in (user_id, user_role.lower())) and not n.get("is_read"):
                    n["is_read"] = True
                    n["read_at"] = now.isoformat() + "Z"
                    c += 1
            return c

    @staticmethod
    def delete_notification(notification_id: int, user_id: str, db: Optional[Session] = None) -> bool:
        """Deletes a notification record."""
        def _delete(session: Session):
            notif = session.query(Notification).filter(Notification.id == notification_id).first()
            if not notif:
                notif = session.query(Notification).filter(Notification.notification_id == str(notification_id)).first()
            if notif:
                session.delete(notif)
                session.commit()
                logger.info("NotificationService: Deleted notification %s", notification_id)
                return True
            return False

        try:
            if db:
                return _delete(db)
            else:
                with get_db() as session:
                    return _delete(session)
        except Exception as e:
            logger.error("NotificationService: Failed to delete notification %s: %s", notification_id, e)
            global notifications_fallback
            notifications_fallback = [
                n for n in notifications_fallback
                if str(n.get("id")) != str(notification_id) and n.get("notification_id") != str(notification_id)
            ]
            return True


# ── Backward Compatibility Standalone Functions ──────────────────────────────

def create_notification(ticket_id: str, recipient: str, message: str) -> dict:
    """Legacy helper function delegating to NotificationService."""
    return NotificationService.create_notification(
        user_id=recipient,
        type="GENERAL",
        title=f"Notification for Ticket {ticket_id}",
        message=message,
        ticket_id=ticket_id
    )

def get_all_notifications() -> List[dict]:
    """Legacy helper returning all notifications."""
    try:
        with get_db() as db:
            records = db.query(Notification).order_by(desc(Notification.created_at)).all()
            return [
                {
                    "id": r.id,
                    "notification_id": r.notification_id or f"NOTIF_{r.id}",
                    "ticket_id": r.ticket_id,
                    "user_id": r.user_id,
                    "recipient": r.recipient or r.user_id,
                    "type": r.type,
                    "title": r.title,
                    "message": r.message,
                    "is_read": bool(r.is_read),
                    "status": r.status or "SENT",
                    "timestamp": r.created_at.isoformat() + "Z" if r.created_at else None
                }
                for r in records
            ]
    except Exception:
        return notifications_fallback

def get_notifications() -> List[dict]:
    return get_all_notifications()
