import logging
import json
import os
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.models.ticket import Ticket
from app.database.models.workflow_models import (
    TicketComment,
    AssignmentHistory,
    DuplicateRelationship,
    CSATSurvey
)
from app.services.timeline_service import TimelineService
from app.services.cluster_service import compute_cosine_similarity
from app.core.logging_context import correlation_id_ctx, user_ctx

logger = logging.getLogger("it-agent-backend")

class WorkflowService:
    # ── COMMENTS & WORK NOTES ────────────────────────────────────────────────
    @staticmethod
    def add_comment(
        db: Session,
        ticket_id: str,
        author: str,
        text: str,
        is_internal: bool,
        role: str
    ) -> TicketComment:
        """
        Adds a comment or internal work note. Restricts internal notes to non-employees.
        """
        if is_internal and role.upper() == "EMPLOYEE":
            raise PermissionError("Employees are not authorized to post or view internal work notes.")

        comment = TicketComment(
            ticket_id=ticket_id,
            author=author,
            text=text,
            is_internal=is_internal,
            correlation_id=correlation_id_ctx.get() or None,
            created_at=datetime.utcnow()
        )
        db.add(comment)
        db.flush()

        # Log timeline event
        event_type = "NOTE_ADDED" if is_internal else "COMMENT_ADDED"
        desc = "Internal work note added." if is_internal else "Customer comment added."
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type=event_type,
            actor=author,
            action="add comment",
            description=desc,
            correlation_id=comment.correlation_id
        )

        return comment

    @staticmethod
    def get_comments(db: Session, ticket_id: str, role: str) -> list[TicketComment]:
        """
        Retrieves comments. Excludes internal work notes if the user is an employee.
        """
        query = db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id)
        if role.upper() == "EMPLOYEE":
            query = query.filter(TicketComment.is_internal == False)
        
        return query.order_by(TicketComment.created_at.asc()).all()

    @staticmethod
    def edit_comment(
        db: Session,
        comment_id: int,
        author: str,
        new_text: str,
        role: str
    ) -> TicketComment:
        """
        Edits an existing comment and stores a JSON history of the modifications.
        """
        comment = db.query(TicketComment).filter(TicketComment.id == comment_id).first()
        if not comment:
            raise ValueError("Comment not found.")

        if comment.is_internal and role.upper() == "EMPLOYEE":
            raise PermissionError("Access denied.")

        # Update edit history JSON
        history = []
        if comment.edited_history:
            try:
                history = json.loads(comment.edited_history)
            except Exception:
                pass
        
        history.append({
            "text": comment.text,
            "edited_at": datetime.utcnow().isoformat(),
            "edited_by": author
        })

        comment.edited_history = json.dumps(history)
        comment.text = new_text
        db.flush()

        # Log timeline event
        event_type = "NOTE_EDITED" if comment.is_internal else "COMMENT_EDITED"
        TimelineService.log_event(
            db=db,
            ticket_id=comment.ticket_id,
            event_type=event_type,
            actor=author,
            action="edit comment",
            description=f"Comment edited by {author}.",
            correlation_id=correlation_id_ctx.get() or None
        )

        return comment

    # ── TICKET REASSIGNMENT ──────────────────────────────────────────────────
    @staticmethod
    def assign_ticket(
        db: Session,
        ticket_id: str,
        new_engineer: str,
        assigned_by: str,
        reason: str = None,
        new_group: str = None
    ) -> Ticket:
        """
        Reassigns a ticket to a new engineer/group and logs assignment history and timeline.
        """
        ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if not ticket:
            raise ValueError("Ticket not found.")

        prev_engineer = ticket.assigned_engineer
        ticket.assigned_engineer = new_engineer
        if new_group:
            ticket.assigned_team = new_group

        # Record assignment log
        hist = AssignmentHistory(
            ticket_id=ticket_id,
            assigned_group=new_group or ticket.assigned_team,
            assigned_engineer=new_engineer,
            assigned_by=assigned_by,
            reason=reason,
            previous_engineer=prev_engineer,
            new_engineer=new_engineer,
            correlation_id=correlation_id_ctx.get() or None
        )
        db.add(hist)
        db.flush()

        # Log timeline event
        desc = f"Assigned to {new_engineer} by {assigned_by}."
        if reason:
            desc += f" Reason: {reason}"
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_REASSIGNED" if prev_engineer else "TICKET_ASSIGNED",
            actor=assigned_by,
            action="assign ticket",
            description=desc,
            correlation_id=hist.correlation_id
        )

        return ticket

    # ── REOPEN WORKFLOW ──────────────────────────────────────────────────────
    @staticmethod
    def reopen_ticket(
        db: Session,
        ticket_id: str,
        reopened_by: str,
        reason: str
    ) -> Ticket:
        """
        Reopens a resolved or closed ticket and increments the reopen count.
        """
        ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if not ticket:
            raise ValueError("Ticket not found.")

        # Backup current resolution info to previous_resolution before clearing
        ticket.previous_resolution = f"State when reopened was {ticket.status}. Reason: {reason}"
        ticket.status = "IN_PROGRESS"
        ticket.reopen_count = (ticket.reopen_count or 0) + 1
        ticket.reopened_by = reopened_by
        ticket.reopened_at = datetime.utcnow()
        ticket.reopen_reason = reason
        
        # Clear resolution and close timestamps
        ticket.resolved_at = None
        ticket.closed_at = None
        db.flush()

        # Log timeline event
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="TICKET_REOPENED",
            actor=reopened_by,
            action="reopen ticket",
            description=f"Ticket reopened by {reopened_by}. Reason: {reason}",
            correlation_id=correlation_id_ctx.get() or None
        )

        return ticket

    # ── DUPLICATE DETECTION ──────────────────────────────────────────────────
    @staticmethod
    def check_duplicate(db: Session, description: str, threshold: float = 0.6) -> list[dict]:
        """
        Detects potential duplicate tickets based on token cosine similarity.
        """
        if not description:
            return []

        # Find all open tickets
        active_tickets = db.query(Ticket).filter(Ticket.status != "CLOSED").all()
        results = []

        for other in active_tickets:
            other_desc = other.description or other.issue_description or ""
            sim = compute_cosine_similarity(description, other_desc)
            if sim >= threshold:
                results.append({
                    "ticket_id": other.ticket_id,
                    "description": other_desc,
                    "status": other.status,
                    "similarity": sim
                })

        # Sort by similarity descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

    @staticmethod
    def confirm_duplicate(db: Session, source_id: str, target_id: str) -> DuplicateRelationship:
        """
        Confirms a duplicate ticket relationship.
        """
        # Ensure target exists
        target = db.query(Ticket).filter(Ticket.ticket_id == target_id).first()
        if not target:
            raise ValueError(f"Target ticket {target_id} not found.")

        rel = db.query(DuplicateRelationship).filter(
            DuplicateRelationship.source_ticket_id == source_id,
            DuplicateRelationship.target_ticket_id == target_id
        ).first()

        if not rel:
            rel = DuplicateRelationship(
                source_ticket_id=source_id,
                target_ticket_id=target_id,
                confidence=1.0,
                status="CONFIRMED",
                created_at=datetime.utcnow()
            )
            db.add(rel)
        else:
            rel.status = "CONFIRMED"

        # Update source ticket status to duplicate (usually resolved as duplicate or linked)
        source = db.query(Ticket).filter(Ticket.ticket_id == source_id).first()
        if source:
            # Associate cluster ID if target has one
            if target.cluster_id:
                source.cluster_id = target.cluster_id
            
            # Log resolution
            source.status = "RESOLVED"
            source.resolved_at = datetime.utcnow()
            source.previous_resolution = f"Marked as duplicate of {target_id}."

        db.flush()

        # Log timeline events
        TimelineService.log_event(
            db=db,
            ticket_id=source_id,
            event_type="DUPLICATE_CONFIRMED",
            actor=user_ctx.get() or "system",
            action="confirm duplicate",
            description=f"Confirmed as duplicate of {target_id}.",
            correlation_id=correlation_id_ctx.get() or None
        )

        return rel

    @staticmethod
    def dismiss_duplicate(db: Session, source_id: str, target_id: str) -> DuplicateRelationship:
        """
        Dismisses a duplicate ticket warning.
        """
        rel = db.query(DuplicateRelationship).filter(
            DuplicateRelationship.source_ticket_id == source_id,
            DuplicateRelationship.target_ticket_id == target_id
        ).first()

        if not rel:
            rel = DuplicateRelationship(
                source_ticket_id=source_id,
                target_ticket_id=target_id,
                confidence=0.0,
                status="DISMISSED",
                created_at=datetime.utcnow()
            )
            db.add(rel)
        else:
            rel.status = "DISMISSED"

        db.flush()

        # Log timeline event
        TimelineService.log_event(
            db=db,
            ticket_id=source_id,
            event_type="DUPLICATE_DISMISSED",
            actor=user_ctx.get() or "system",
            action="dismiss duplicate",
            description=f"Dismissed duplicate relation warning for ticket {target_id}.",
            correlation_id=correlation_id_ctx.get() or None
        )

        return rel

    # ── CSAT & SURVEY SUBMISSION ──────────────────────────────────────────────
    @staticmethod
    def submit_csat(
        db: Session,
        ticket_id: str,
        rating: int,
        feedback: str = None,
        response_time_rating: int = None,
        resolution_quality_rating: int = None,
        would_recommend: bool = True
    ) -> CSATSurvey:
        """
        Submits post-close CSAT survey.
        """
        ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if not ticket:
            raise ValueError("Ticket not found.")
        if ticket.status != "CLOSED":
            raise ValueError("CSAT surveys can only be submitted for CLOSED tickets.")

        # Check if survey already exists
        existing = db.query(CSATSurvey).filter(CSATSurvey.ticket_id == ticket_id).first()
        if existing:
            raise ValueError("CSAT survey has already been submitted for this ticket.")

        survey = CSATSurvey(
            ticket_id=ticket_id,
            rating=rating,
            feedback=feedback,
            response_time_rating=response_time_rating,
            resolution_quality_rating=resolution_quality_rating,
            would_recommend=would_recommend,
            created_at=datetime.utcnow()
        )
        db.add(survey)
        db.flush()

        # Log timeline event
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="CSAT_SUBMITTED",
            actor=ticket.created_by or "customer",
            action="submit csat",
            description=f"CSAT rating of {rating}/5 submitted.",
            correlation_id=correlation_id_ctx.get() or None
        )

        return survey

    # ── EXECUTIVE METRICS DASHBOARD ──────────────────────────────────────────
    @staticmethod
    def get_executive_metrics(db: Session) -> dict:
        """
        Compiles core operations SLA, workload aging, and CSAT metrics.
        """
        tickets = db.query(Ticket).all()
        now = datetime.utcnow()

        # 1. MTTR and MTTResp calculations
        resolution_durations = []
        response_durations = []

        # We compute response duration as duration between created_at and ticket assignment/timeline update
        # For simplicity, we fallback to time from created_at to first assignment history or 300s default if active.
        for ticket in tickets:
            if ticket.status in ("RESOLVED", "CLOSED") and ticket.resolved_at:
                resolution_durations.append((ticket.resolved_at - ticket.created_at).total_seconds())
            elif ticket.status == "CLOSED" and ticket.closed_at:
                resolution_durations.append((ticket.closed_at - ticket.created_at).total_seconds())

            # Response time estimate: check if ticket has an assigned engineer
            # If so, estimate response as elapsed time since creation or use history log
            if ticket.assigned_engineer:
                hist = db.query(AssignmentHistory).filter(AssignmentHistory.ticket_id == ticket.ticket_id).order_by(AssignmentHistory.assigned_time.asc()).first()
                if hist:
                    response_durations.append((hist.assigned_time - ticket.created_at).total_seconds())
                else:
                    response_durations.append(300.0) # default fallback

        avg_mttr_hours = (sum(resolution_durations) / len(resolution_durations) / 3600.0) if resolution_durations else 0.0
        avg_mttresp_mins = (sum(response_durations) / len(response_durations) / 60.0) if response_durations else 0.0

        # 2. SLA risks
        sla_breaches = sum(1 for t in tickets if t.sla_breached)
        total_tickets = len(tickets)
        sla_compliance_rate = ((total_tickets - sla_breaches) / total_tickets * 100.0) if total_tickets else 100.0

        # 3. Workload aging buckets (for open/active tickets)
        active_tickets = [t for t in tickets if t.status not in ("RESOLVED", "CLOSED")]
        aging_buckets = {
            "0-4h": 0,
            "4-8h": 0,
            "8-24h": 0,
            "1-3d": 0,
            "3-7d": 0,
            "7d+": 0
        }

        for t in active_tickets:
            age = now - t.created_at
            hours = age.total_seconds() / 3600.0
            if hours <= 4:
                aging_buckets["0-4h"] += 1
            elif hours <= 8:
                aging_buckets["4-8h"] += 1
            elif hours <= 24:
                aging_buckets["8-24h"] += 1
            elif hours <= 72:
                aging_buckets["1-3d"] += 1
            elif hours <= 168:
                aging_buckets["3-7d"] += 1
            else:
                aging_buckets["7d+"] += 1

        # 4. CSAT Averages
        surveys = db.query(CSATSurvey).all()
        avg_csat = sum(s.rating for s in surveys) / len(surveys) if surveys else 0.0
        recommendation_rate = (sum(1 for s in surveys if s.would_recommend) / len(surveys) * 100.0) if surveys else 100.0

        return {
            "avg_mttr_hours": round(avg_mttr_hours, 2),
            "avg_mttresp_mins": round(avg_mttresp_mins, 2),
            "sla_compliance_rate": round(sla_compliance_rate, 2),
            "total_breached_slas": sla_breaches,
            "aging_buckets": aging_buckets,
            "avg_csat": round(avg_csat, 2),
            "recommendation_rate": round(recommendation_rate, 2),
            "total_csat_submissions": len(surveys)
        }
