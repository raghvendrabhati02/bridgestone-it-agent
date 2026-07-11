from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from datetime import datetime, timedelta
from typing import Optional
import json

from app.core.security import get_db_context
from app.database.models.execution_history import ExecutionHistory
from app.database.models.device import Device
from app.database.models.user import User
from app.main import get_current_user

router = APIRouter(prefix="/api/executions", tags=["Executions"])

@router.get("")
def get_executions(
    search: Optional[str] = None,
    employee: Optional[str] = None,
    hostname: Optional[str] = None,
    department: Optional[str] = None,
    action: Optional[str] = None,
    status_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "timestamp",
    sort_order: str = "desc",
    page: int = 1,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Admin role required."
        )

    query = db.query(ExecutionHistory)

    # 1. Search (Execution ID, Employee/Username, Hostname/Device ID)
    if search:
        if search.isdigit():
            query = query.filter(
                (ExecutionHistory.id == int(search)) |
                (ExecutionHistory.username.ilike(f"%{search}%")) |
                (ExecutionHistory.device_id.ilike(f"%{search}%"))
            )
        else:
            query = query.filter(
                (ExecutionHistory.username.ilike(f"%{search}%")) |
                (ExecutionHistory.device_id.ilike(f"%{search}%")) |
                (ExecutionHistory.action_name.ilike(f"%{search}%"))
            )

    # 2. Filters
    if employee:
        query = query.filter(ExecutionHistory.username == employee)
    if hostname:
        query = query.filter(ExecutionHistory.device_id == hostname)
    if department:
        query = query.filter(ExecutionHistory.department == department)
    if action:
        query = query.filter(ExecutionHistory.action_name == action)
    if status_filter:
        query = query.filter(ExecutionHistory.status.ilike(status_filter))

    # Date Range filtering
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", ""))
            query = query.filter(ExecutionHistory.timestamp >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", ""))
            query = query.filter(ExecutionHistory.timestamp <= end_dt)
        except ValueError:
            pass

    # 3. Sorting
    sort_col = getattr(ExecutionHistory, sort_by, ExecutionHistory.timestamp)
    if sort_order == "asc":
        query = query.order_by(asc(sort_col))
    else:
        query = query.order_by(desc(sort_col))

    # 4. Pagination
    total_count = query.count()
    offset = (page - 1) * limit
    executions = query.offset(offset).limit(limit).all()

    # Format result
    results = []
    for e in executions:
        params = {}
        if e.parameters:
            try:
                params = json.loads(e.parameters)
            except Exception:
                params = {"raw": e.parameters}

        results.append({
            "id": e.id,
            "timestamp": e.timestamp.isoformat() + "Z",
            "username": e.username,
            "device_id": e.device_id,
            "department": e.department or "Unknown",
            "action_name": e.action_name,
            "status": e.status,
            "result": e.result,
            "duration": e.duration,
            "agent_version": e.agent_version or "1.0",
            "parameters": params,
            "started_at": e.started_at.isoformat() + "Z" if e.started_at else None,
            "completed_at": e.completed_at.isoformat() + "Z" if e.completed_at else None,
            "logs": e.logs
        })

    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "executions": results
    }

@router.get("/statistics")
def get_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Admin role required."
        )

    all_history = db.query(ExecutionHistory).all()
    total = len(all_history)

    success_count = sum(1 for e in all_history if e.status == "Success")
    failed_count = sum(1 for e in all_history if e.status == "Failed")
    running_count = sum(1 for e in all_history if e.status == "Running")
    cancelled_count = sum(1 for e in all_history if e.status == "Cancelled")
    pending_count = sum(1 for e in all_history if e.status == "Pending")

    success_rate = (success_count / total * 100) if total > 0 else 0.0
    failure_rate = (failed_count / total * 100) if total > 0 else 0.0
    
    durations = [e.duration for e in all_history if e.status == "Success" and e.duration > 0]
    avg_duration = (sum(durations) / len(durations)) if durations else 0.0

    # Today's executions
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    todays_count = sum(1 for e in all_history if e.timestamp >= today_start)

    # Action usage stats
    action_counts = {}
    for e in all_history:
        action_counts[e.action_name] = action_counts.get(e.action_name, 0) + 1

    most_used = "None"
    least_used = "None"
    if action_counts:
        sorted_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)
        most_used = sorted_actions[0][0]
        least_used = sorted_actions[-1][0]

    return {
        "total_executions": total,
        "success_rate": round(success_rate, 2),
        "failure_rate": round(failure_rate, 2),
        "average_duration": round(avg_duration, 2),
        "most_used_action": most_used,
        "least_used_action": least_used,
        "successful_actions": success_count,
        "failed_actions": failed_count,
        "running_actions": running_count,
        "cancelled_actions": cancelled_count,
        "pending_actions": pending_count,
        "todays_executions": todays_count
    }

@router.get("/{id}")
def get_execution_details(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_context)
):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Admin role required."
        )

    e = db.query(ExecutionHistory).filter(ExecutionHistory.id == id).first()
    if not e:
        raise HTTPException(
            status_code=404,
            detail=f"Execution with ID {id} not found."
        )

    params = {}
    if e.parameters:
        try:
            params = json.loads(e.parameters)
        except Exception:
            params = {"raw": e.parameters}

    return {
        "id": e.id,
        "timestamp": e.timestamp.isoformat() + "Z",
        "username": e.username,
        "device_id": e.device_id,
        "department": e.department or "Unknown",
        "action_name": e.action_name,
        "status": e.status,
        "result": e.result,
        "duration": e.duration,
        "agent_version": e.agent_version or "1.0",
        "parameters": params,
        "started_at": e.started_at.isoformat() + "Z" if e.started_at else None,
        "completed_at": e.completed_at.isoformat() + "Z" if e.completed_at else None,
        "logs": e.logs
    }
