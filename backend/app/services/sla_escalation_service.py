"""
SLA Escalation Service
======================
Production-grade SLA monitoring engine called by the APScheduler job
(sla_monitor_job.py) every 60 seconds.

Architecture
------------
run_full_sla_evaluation()          ← entry point from scheduler job
  └─► for each open ticket:
        evaluate_ticket(db, ticket)
          ├─ compute_sla_status(ticket)   → elapsed / remaining / pct / state
          ├─ update Ticket.sla_state + sla_breached_at in DB
          ├─ handle_warning_75()          → dedup-guarded notification + RBAC
          ├─ handle_warning_90()          → same
          ├─ handle_breach()              → mark breached + EscalationHistory L1
          └─ handle_escalation_levels()  → L2 at +30min, L3 at +60min

SLA States
----------
HEALTHY | WARNING_75 | WARNING_90 | BREACHED |
ESCALATED_LEVEL_1 | ESCALATED_LEVEL_2 | ESCALATED_LEVEL_3

Notification recipients
-----------------------
WARNING_75            : assigned_team, Manager
WARNING_90            : assigned_team, Manager, Admin
BREACHED & escalations: assigned_team, Manager, Admin

Escalation timeline
-------------------
Level 1 : immediately on breach
Level 2 : sla_breached_at + 30 min
Level 3 : sla_breached_at + 60 min
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("it-agent-backend")

# ── SLA State constants ───────────────────────────────────────────────────────

HEALTHY           = "HEALTHY"
WARNING_75        = "WARNING_75"
WARNING_90        = "WARNING_90"
BREACHED          = "BREACHED"
ESCALATED_LEVEL_1 = "ESCALATED_LEVEL_1"
ESCALATED_LEVEL_2 = "ESCALATED_LEVEL_2"
ESCALATED_LEVEL_3 = "ESCALATED_LEVEL_3"

# Audit event type strings (must match SlaAuditEvent.event_type vocabulary)
_EVT_W75  = "WARNING_75"
_EVT_W90  = "WARNING_90"
_EVT_BRE  = "BREACHED"
_EVT_ESC1 = "ESCALATED_L1"
_EVT_ESC2 = "ESCALATED_L2"
_EVT_ESC3 = "ESCALATED_L3"

# Escalation timing (minutes after first breach)
_L2_MINUTES = 30
_L3_MINUTES = 60

# Recipients
_RECIPIENTS_W75  = ["Manager"]
_RECIPIENTS_W90  = ["Manager", "Admin"]
_RECIPIENTS_BREACH = ["Manager", "Admin"]


# ── Public helper: compute SLA status ────────────────────────────────────────

def compute_sla_status(ticket) -> Dict[str, Any]:
    """
    Compute SLA timing metrics for a single Ticket ORM object.

    Returns a dict with:
        elapsed_hours   : float  – hours since ticket creation
        remaining_hours : float  – hours until SLA deadline (negative = past)
        sla_pct         : float  – percentage of SLA window consumed [0..∞]
        sla_state       : str    – one of the SLA State constants above
        sla_hours       : int    – configured SLA window (default 24h)
    """
    now = datetime.utcnow()
    created = getattr(ticket, "created_at", None)
    if not created:
        return {
            "elapsed_hours": 0.0,
            "remaining_hours": 0.0,
            "sla_pct": 0.0,
            "sla_state": HEALTHY,
            "sla_hours": 24,
        }

    sla_hours: int = ticket.sla_hours or 24
    elapsed_hours: float = (now - created).total_seconds() / 3600.0
    remaining_hours: float = sla_hours - elapsed_hours
    sla_pct: float = (elapsed_hours / sla_hours) * 100.0 if sla_hours > 0 else 100.0

    # Determine state based on current escalation persisted in DB
    # (use the stored sla_state as the floor; we can only upgrade)
    current_db_state = getattr(ticket, "sla_state", None) or HEALTHY

    if sla_pct < 75.0:
        state = HEALTHY
    elif sla_pct < 90.0:
        state = WARNING_75
    elif sla_pct < 100.0:
        state = WARNING_90
    else:
        # Once breached, defer to whatever escalation level is persisted
        if current_db_state in (ESCALATED_LEVEL_1, ESCALATED_LEVEL_2, ESCALATED_LEVEL_3):
            state = current_db_state
        else:
            state = BREACHED

    return {
        "elapsed_hours": round(elapsed_hours, 4),
        "remaining_hours": round(remaining_hours, 4),
        "sla_pct": round(sla_pct, 2),
        "sla_state": state,
        "sla_hours": sla_hours,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _send_notifications(ticket_id: str, recipients: List[str], message: str) -> None:
    """Fire notifications to every recipient. Non-fatal."""
    try:
        from app.services.notification_service import create_notification
        for recipient in recipients:
            try:
                create_notification(ticket_id=ticket_id, recipient=recipient, message=message)
            except Exception as ne:
                logger.error("SLA Escalation: Notification to '%s' failed for %s: %s", recipient, ticket_id, ne)
    except Exception as e:
        logger.error("SLA Escalation: _send_notifications import/call failed: %s", e)


def _log_rbac(
    ticket_id: str,
    action: str,
    old_state: str,
    new_state: str,
    details: Dict[str, Any],
) -> None:
    """Write an RBAC audit log entry. Non-fatal."""
    try:
        from app.services.rbac_audit_service import log_rbac_event
        log_rbac_event(
            user="sla_monitor_job",
            role="SYSTEM",
            action=action,
            ticket_id=ticket_id,
            old_state=old_state,
            new_state=new_state,
            details=details,
        )
    except Exception as e:
        logger.error("SLA Escalation: RBAC audit log failed for %s: %s", ticket_id, e)


def _has_audit_event(db, ticket_id: str, event_type: str) -> bool:
    try:
        from app.database.repositories.sla_audit_event_repository import SlaAuditEventRepository
        repo = SlaAuditEventRepository(db)
        return repo.has_event(ticket_id, event_type)
    except Exception:
        return False


def _record_audit_event(db, ticket_id: str, event_type: str) -> None:
    try:
        from app.database.repositories.sla_audit_event_repository import SlaAuditEventRepository
        repo = SlaAuditEventRepository(db)
        repo.record_event(ticket_id, event_type)
    except Exception as e:
        logger.error("SLA Escalation: Failed to record audit event %s for %s: %s", event_type, ticket_id, e)


def _increment_prometheus_breach() -> None:
    try:
        from app.core.metrics import BUSINESS_SLA_BREACHES_TOTAL
        BUSINESS_SLA_BREACHES_TOTAL.inc()
    except Exception:
        pass


# ── Milestone handlers ────────────────────────────────────────────────────────

def _handle_warning_75(db, ticket, sla_info: Dict[str, Any]) -> None:
    """Fire WARNING_75 notifications once per ticket (dedup via SlaAuditEvent)."""
    ticket_id = ticket.ticket_id
    if _has_audit_event(db, ticket_id, _EVT_W75):
        return

    team = ticket.assigned_team or "IT Support"
    msg = (
        f"⚠️ SLA Warning: Ticket {ticket_id} ({ticket.category}) has consumed "
        f"{sla_info['sla_pct']:.1f}% of its {sla_info['sla_hours']}h SLA. "
        f"{sla_info['remaining_hours']:.1f}h remaining."
    )
    recipients = [team] + _RECIPIENTS_W75
    _send_notifications(ticket_id, recipients, msg)
    _record_audit_event(db, ticket_id, _EVT_W75)
    _log_rbac(
        ticket_id=ticket_id,
        action="SLA_WARNING_75",
        old_state=HEALTHY,
        new_state=WARNING_75,
        details={
            "sla_pct": sla_info["sla_pct"],
            "elapsed_hours": sla_info["elapsed_hours"],
            "sla_hours": sla_info["sla_hours"],
        },
    )
    logger.info("SLA Escalation: WARNING_75 fired for %s (%.1f%% consumed)", ticket_id, sla_info["sla_pct"])


def _handle_warning_90(db, ticket, sla_info: Dict[str, Any]) -> None:
    """Fire WARNING_90 notifications once per ticket (dedup via SlaAuditEvent)."""
    ticket_id = ticket.ticket_id
    if _has_audit_event(db, ticket_id, _EVT_W90):
        return

    team = ticket.assigned_team or "IT Support"
    msg = (
        f"🚨 SLA Critical Warning: Ticket {ticket_id} ({ticket.category}) has consumed "
        f"{sla_info['sla_pct']:.1f}% of its {sla_info['sla_hours']}h SLA. "
        f"Immediate action required — {sla_info['remaining_hours']:.1f}h left."
    )
    recipients = [team] + _RECIPIENTS_W90
    _send_notifications(ticket_id, recipients, msg)
    _record_audit_event(db, ticket_id, _EVT_W90)
    _log_rbac(
        ticket_id=ticket_id,
        action="SLA_WARNING_90",
        old_state=WARNING_75,
        new_state=WARNING_90,
        details={
            "sla_pct": sla_info["sla_pct"],
            "elapsed_hours": sla_info["elapsed_hours"],
            "sla_hours": sla_info["sla_hours"],
        },
    )
    logger.info("SLA Escalation: WARNING_90 fired for %s (%.1f%% consumed)", ticket_id, sla_info["sla_pct"])


def _handle_breach(db, ticket, sla_info: Dict[str, Any]) -> None:
    """
    Mark ticket as breached (sla_breached=True, sla_breached_at) and
    create Level-1 escalation record. Fires once per ticket.
    """
    ticket_id = ticket.ticket_id

    # Set breach timestamp if not yet set
    if not getattr(ticket, "sla_breached_at", None):
        ticket.sla_breached_at = datetime.utcnow()
        ticket.sla_breached = True
        db.commit()

    if _has_audit_event(db, ticket_id, _EVT_BRE):
        return

    team = ticket.assigned_team or "IT Support"
    msg = (
        f"🆘 SLA BREACHED: Ticket {ticket_id} ({ticket.category}, Priority: {ticket.priority}) "
        f"has exceeded its {sla_info['sla_hours']}h SLA by "
        f"{abs(sla_info['remaining_hours']):.1f}h. Escalated to Level 1."
    )
    recipients = [team] + _RECIPIENTS_BREACH
    _send_notifications(ticket_id, recipients, msg)
    _record_audit_event(db, ticket_id, _EVT_BRE)
    _increment_prometheus_breach()

    # Create Level 1 escalation history
    _create_escalation_level(
        db=db,
        ticket_id=ticket_id,
        level=1,
        reason=f"SLA breached after {sla_info['elapsed_hours']:.2f}h (limit: {sla_info['sla_hours']}h)",
        sla_info=sla_info,
        evt_type=_EVT_ESC1,
        old_state=WARNING_90,
    )

    logger.warning(
        "SLA Escalation: BREACHED fired for %s — %.2fh elapsed, %dh SLA",
        ticket_id, sla_info["elapsed_hours"], sla_info["sla_hours"],
    )


def _handle_escalation_levels(db, ticket, sla_info: Dict[str, Any]) -> None:
    """
    Check and trigger Level 2 (+30 min) and Level 3 (+60 min) post-breach.
    """
    breached_at = getattr(ticket, "sla_breached_at", None)
    if not breached_at:
        return

    now = datetime.utcnow()
    minutes_since_breach = (now - breached_at).total_seconds() / 60.0

    # Level 2: 30 min post breach
    if minutes_since_breach >= _L2_MINUTES and not _has_audit_event(db, ticket.ticket_id, _EVT_ESC2):
        _create_escalation_level(
            db=db,
            ticket_id=ticket.ticket_id,
            level=2,
            reason=f"SLA escalation Level 2 — {minutes_since_breach:.0f} min since breach",
            sla_info=sla_info,
            evt_type=_EVT_ESC2,
            old_state=ESCALATED_LEVEL_1,
        )

    # Level 3: 60 min post breach
    if minutes_since_breach >= _L3_MINUTES and not _has_audit_event(db, ticket.ticket_id, _EVT_ESC3):
        _create_escalation_level(
            db=db,
            ticket_id=ticket.ticket_id,
            level=3,
            reason=f"SLA escalation Level 3 — {minutes_since_breach:.0f} min since breach",
            sla_info=sla_info,
            evt_type=_EVT_ESC3,
            old_state=ESCALATED_LEVEL_2,
        )


def _create_escalation_level(
    db,
    ticket_id: str,
    level: int,
    reason: str,
    sla_info: Dict[str, Any],
    evt_type: str,
    old_state: str,
) -> None:
    """
    Shared helper: persist SlaEscalationHistory, send notifications,
    record audit event, and write RBAC log.
    """
    try:
        from app.database.repositories.sla_escalation_repository import SlaEscalationRepository
        esc_repo = SlaEscalationRepository(db)

        if esc_repo.has_level(ticket_id, level):
            return  # Double-check at repo layer

        new_state = {1: ESCALATED_LEVEL_1, 2: ESCALATED_LEVEL_2, 3: ESCALATED_LEVEL_3}.get(level, ESCALATED_LEVEL_1)

        esc_repo.save(
            ticket_id=ticket_id,
            level=level,
            reason=reason,
            triggered_by="sla_monitor_job",
            notification_sent=True,
            audit_logged=True,
        )
        _record_audit_event(db, ticket_id, evt_type)

        # Update ticket sla_state in DB
        from app.database.models.ticket import Ticket
        ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if ticket:
            ticket.sla_state = new_state
            db.commit()

        # Notifications
        from app.database.models.ticket import Ticket as T
        t = db.query(T).filter(T.ticket_id == ticket_id).first()
        team = (t.assigned_team if t else None) or "IT Support"
        msg = (
            f"📢 SLA Escalation Level {level}: Ticket {ticket_id} "
            f"({sla_info['elapsed_hours']:.1f}h elapsed, SLA: {sla_info['sla_hours']}h). "
            f"{reason}"
        )
        _send_notifications(ticket_id, [team] + _RECIPIENTS_BREACH, msg)

        _log_rbac(
            ticket_id=ticket_id,
            action=f"SLA_ESCALATION_LEVEL_{level}",
            old_state=old_state,
            new_state=new_state,
            details={
                "level": level,
                "sla_pct": sla_info["sla_pct"],
                "elapsed_hours": sla_info["elapsed_hours"],
                "sla_hours": sla_info["sla_hours"],
                "reason": reason,
            },
        )
        logger.warning("SLA Escalation: Level %d created for %s", level, ticket_id)

    except Exception as e:
        logger.error("SLA Escalation: Failed to create Level %d escalation for %s: %s", level, ticket_id, e)


# ── Per-ticket evaluation ─────────────────────────────────────────────────────

def evaluate_ticket(db, ticket) -> Dict[str, Any]:
    """
    Full SLA evaluation for a single ticket. Updates sla_state in DB,
    fires appropriate milestone actions, and returns the computed status dict.
    """
    try:
        sla_info = compute_sla_status(ticket)
        old_state = getattr(ticket, "sla_state", HEALTHY) or HEALTHY
        new_state = sla_info["sla_state"]

        # Update ticket sla_state in DB (always keep it current)
        if ticket.sla_state != new_state:
            ticket.sla_state = new_state
            db.commit()

        # Route to the correct milestone handler
        if sla_info["sla_pct"] >= 100.0:
            _handle_breach(db, ticket, sla_info)
            _handle_escalation_levels(db, ticket, sla_info)
            # Refresh state after potential level updates
            sla_info["sla_state"] = ticket.sla_state or new_state
        elif sla_info["sla_pct"] >= 90.0:
            _handle_warning_90(db, ticket, sla_info)
        elif sla_info["sla_pct"] >= 75.0:
            _handle_warning_75(db, ticket, sla_info)

        return sla_info

    except Exception as e:
        logger.error("SLA Escalation: evaluate_ticket failed for %s: %s", getattr(ticket, "ticket_id", "?"), e)
        return {}


# ── Main entry point ──────────────────────────────────────────────────────────

def run_full_sla_evaluation() -> Dict[str, Any]:
    """
    Entry point called by the sla_monitor_job every 60 seconds.

    Queries all open tickets, evaluates SLA status for each, and returns
    a summary dict with counts.
    """
    logger.info("SLA Escalation Service: Starting full evaluation run...")
    summary: Dict[str, Any] = {
        "evaluated": 0,
        "healthy": 0,
        "warning_75": 0,
        "warning_90": 0,
        "breached": 0,
        "escalated": 0,
        "errors": 0,
    }

    try:
        from app.database.session import get_db
        from app.database.models.ticket import Ticket

        with get_db() as db:
            active_tickets = (
                db.query(Ticket)
                .filter(Ticket.status.in_(["OPEN", "ASSIGNED", "IN_PROGRESS"]))
                .all()
            )
            logger.info("SLA Escalation: Evaluating %d active tickets", len(active_tickets))

            for ticket in active_tickets:
                if not ticket.created_at:
                    continue
                try:
                    sla_info = evaluate_ticket(db, ticket)
                    summary["evaluated"] += 1
                    state = sla_info.get("sla_state", HEALTHY)
                    if state == HEALTHY:
                        summary["healthy"] += 1
                    elif state == WARNING_75:
                        summary["warning_75"] += 1
                    elif state == WARNING_90:
                        summary["warning_90"] += 1
                    elif state == BREACHED:
                        summary["breached"] += 1
                    elif state in (ESCALATED_LEVEL_1, ESCALATED_LEVEL_2, ESCALATED_LEVEL_3):
                        summary["escalated"] += 1
                except Exception as te:
                    summary["errors"] += 1
                    logger.error("SLA Escalation: Error evaluating ticket %s: %s", ticket.ticket_id, te)

    except Exception as e:
        logger.error("SLA Escalation: run_full_sla_evaluation outer error: %s", e)
        raise

    logger.info("SLA Escalation: Evaluation complete — %s", summary)
    return summary


# ── Dashboard / reporting ─────────────────────────────────────────────────────

def get_dashboard_metrics() -> Dict[str, Any]:
    """
    Returns aggregated SLA metrics for the dashboard endpoint.

    Counts are derived from the current sla_state on each ticket:
      healthy / warning_75 / warning_90 / breached / escalated_l1/l2/l3
    Compliance % = (non-breached active tickets / total active tickets) * 100
    """
    try:
        from app.database.session import get_db
        from app.database.models.ticket import Ticket

        with get_db() as db:
            all_tickets = db.query(Ticket).all()
            active_tickets = [
                t for t in all_tickets
                if t.status in ("OPEN", "ASSIGNED", "IN_PROGRESS")
            ]
            resolved_today = [
                t for t in all_tickets
                if t.status in ("RESOLVED", "CLOSED")
            ]

            counts = {
                "healthy":          0,
                "warning_75":       0,
                "warning_90":       0,
                "breached":         0,
                "escalated_l1":     0,
                "escalated_l2":     0,
                "escalated_l3":     0,
            }

            for t in active_tickets:
                state = t.sla_state or HEALTHY
                if state == HEALTHY:
                    counts["healthy"] += 1
                elif state == WARNING_75:
                    counts["warning_75"] += 1
                elif state == WARNING_90:
                    counts["warning_90"] += 1
                elif state == BREACHED:
                    counts["breached"] += 1
                elif state == ESCALATED_LEVEL_1:
                    counts["escalated_l1"] += 1
                elif state == ESCALATED_LEVEL_2:
                    counts["escalated_l2"] += 1
                elif state == ESCALATED_LEVEL_3:
                    counts["escalated_l3"] += 1

            total_active = len(active_tickets)
            breached_total = (
                counts["breached"]
                + counts["escalated_l1"]
                + counts["escalated_l2"]
                + counts["escalated_l3"]
            )
            compliance_pct = (
                round(((total_active - breached_total) / total_active) * 100, 1)
                if total_active > 0
                else 100.0
            )

            # Average resolution time for resolved tickets (approx)
            avg_resolution_hours = 0.0
            resolved_with_times = [
                t for t in resolved_today
                if t.created_at
            ]
            if resolved_with_times:
                now = datetime.utcnow()
                total_secs = sum(
                    (now - t.created_at).total_seconds()
                    for t in resolved_with_times
                )
                avg_resolution_hours = round(total_secs / len(resolved_with_times) / 3600, 2)

            # Average SLA usage % for active tickets
            avg_sla_usage_pct = 0.0
            if active_tickets:
                pcts = []
                for t in active_tickets:
                    info = compute_sla_status(t)
                    pcts.append(info["sla_pct"])
                avg_sla_usage_pct = round(sum(pcts) / len(pcts), 1)

            return {
                "open": total_active,
                "resolved_today": len(resolved_today),
                "healthy": counts["healthy"],
                "warning_75": counts["warning_75"],
                "warning_90": counts["warning_90"],
                "breached": counts["breached"],
                "escalated_l1": counts["escalated_l1"],
                "escalated_l2": counts["escalated_l2"],
                "escalated_l3": counts["escalated_l3"],
                "avg_resolution_hours": avg_resolution_hours,
                "avg_sla_usage_pct": avg_sla_usage_pct,
                "compliance_pct": compliance_pct,
            }

    except Exception as e:
        logger.error("SLA Escalation: get_dashboard_metrics failed: %s", e)
        return {
            "open": 0, "resolved_today": 0,
            "healthy": 0, "warning_75": 0, "warning_90": 0,
            "breached": 0, "escalated_l1": 0, "escalated_l2": 0, "escalated_l3": 0,
            "avg_resolution_hours": 0.0, "avg_sla_usage_pct": 0.0,
            "compliance_pct": 100.0,
        }


def get_escalation_history() -> List[Dict[str, Any]]:
    """
    Returns all SLA escalation records for dashboard display.
    Ordered newest-first.
    """
    try:
        from app.database.session import get_db
        from app.database.repositories.sla_escalation_repository import SlaEscalationRepository

        with get_db() as db:
            repo = SlaEscalationRepository(db)
            records = repo.get_all()
            return [
                {
                    "id": r.id,
                    "ticket_id": r.ticket_id,
                    "level": r.level,
                    "reason": r.reason,
                    "triggered_by": r.triggered_by,
                    "notification_sent": r.notification_sent,
                    "audit_logged": r.audit_logged,
                    "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
                }
                for r in records
            ]
    except Exception as e:
        logger.error("SLA Escalation: get_escalation_history failed: %s", e)
        return []


def get_sla_status_for_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns the current SLA status for a specific ticket.
    Used by GET /sla/ticket/{ticket_id} endpoint.
    """
    try:
        from app.database.session import get_db
        from app.database.models.ticket import Ticket

        with get_db() as db:
            ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
            if not ticket:
                return None

            sla_info = compute_sla_status(ticket)
            return {
                "ticket_id": ticket_id,
                "category": ticket.category,
                "priority": ticket.priority,
                "assigned_team": ticket.assigned_team,
                "sla_hours": ticket.sla_hours,
                "sla_state": sla_info["sla_state"],
                "elapsed_hours": sla_info["elapsed_hours"],
                "remaining_hours": sla_info["remaining_hours"],
                "sla_pct": sla_info["sla_pct"],
                "sla_breached": ticket.sla_breached or False,
                "sla_breached_at": (
                    ticket.sla_breached_at.isoformat() + "Z"
                    if ticket.sla_breached_at else None
                ),
            }
    except Exception as e:
        logger.error("SLA Escalation: get_sla_status_for_ticket failed for %s: %s", ticket_id, e)
        return None
