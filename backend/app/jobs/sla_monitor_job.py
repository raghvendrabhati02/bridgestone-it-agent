import logging

logger = logging.getLogger("it-agent-backend")


def run_sla_monitor_job() -> None:
    """
    SLA Monitor Job — thin scheduler entry point.

    All evaluation logic, deduplication, notifications, escalation level
    creation, and RBAC audit logging is delegated to SlaEscalationService.
    The old in-memory _breached_tickets set has been removed; deduplication
    is now DB-backed via the sla_audit_events table.

    The Prometheus BUSINESS_SLA_BREACHES_TOTAL counter is incremented
    inside sla_escalation_service._handle_breach(), so no double-counting
    occurs here.
    """
    logger.info("SLA Monitor Job: starting run (delegating to SlaEscalationService).")
    try:
        from app.services.sla_escalation_service import run_full_sla_evaluation
        summary = run_full_sla_evaluation()
        logger.info(
            "SLA Monitor Job: completed. evaluated=%d healthy=%d w75=%d w90=%d "
            "breached=%d escalated=%d errors=%d",
            summary.get("evaluated", 0),
            summary.get("healthy", 0),
            summary.get("warning_75", 0),
            summary.get("warning_90", 0),
            summary.get("breached", 0),
            summary.get("escalated", 0),
            summary.get("errors", 0),
        )
    except Exception as e:
        logger.error("SLA Monitor Job: failed with exception: %s", e)
        raise
