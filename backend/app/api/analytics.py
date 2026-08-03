from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging

from app.core.security import RoleChecker, get_db_context, User
from app.services import analytics_service

logger = logging.getLogger("it-agent-backend")

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
admin_or_manager = RoleChecker(["ADMIN", "MANAGER"])

@router.get("/overview")
def get_overview(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/overview': Requested by user %s", current_user.username)
    return analytics_service.get_overview_metrics(db)


@router.get("/dashboard")
def get_dashboard_analytics_api(
    time_filter: str | None = "month",
    start_date: str | None = None,
    end_date: str | None = None,
    department: str | None = None,
    assignment_group: str | None = None,
    category: str | None = None,
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/dashboard': Requested by user %s", current_user.username)
    return analytics_service.get_dashboard_analytics(
        db=db,
        time_filter=time_filter,
        start_date=start_date,
        end_date=end_date,
        department=department,
        assignment_group=assignment_group,
        category=category
    )


@router.get("/tickets")
def get_tickets(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/tickets': Requested by user %s", current_user.username)
    return analytics_service.get_ticket_metrics(db)

@router.get("/sla")
def get_sla(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/sla': Requested by user %s", current_user.username)
    return analytics_service.get_sla_metrics(db)

@router.get("/teams")
def get_teams(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/teams': Requested by user %s", current_user.username)
    return analytics_service.get_team_metrics(db)

@router.get("/categories")
def get_categories(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/categories': Requested by user %s", current_user.username)
    return analytics_service.get_category_metrics(db)

@router.get("/security")
def get_security(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/security': Requested by user %s", current_user.username)
    return analytics_service.get_security_metrics(db)

@router.get("/root-causes")
def get_root_causes(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/root-causes': Requested by user %s", current_user.username)
    return analytics_service.get_root_cause_metrics(db)

@router.get("/users")
def get_users(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/users': Requested by user %s", current_user.username)
    return analytics_service.get_user_metrics(db)

@router.get("/service-requests")
def get_service_requests(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/service-requests': Requested by user %s", current_user.username)
    return analytics_service.get_service_request_metrics(db)


@router.get("/engine-observability")
def get_engine_observability(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/engine-observability': Requested by user %s", current_user.username)
    return analytics_service.get_engine_observability_metrics(db)


@router.get("/approvals")
def get_approvals(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/approvals': Requested by user %s", current_user.username)
    return analytics_service.get_approval_metrics(db)


@router.get("/assignment-groups")
def get_assignment_groups(
    current_user: User = Depends(admin_or_manager),
    db: Session = Depends(get_db_context)
):
    logger.info("FastAPI Endpoint GET '/api/analytics/assignment-groups': Requested by user %s", current_user.username)
    return analytics_service.get_assignment_group_metrics(db)

