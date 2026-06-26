from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from datetime import datetime
from app.database.base import Base

class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(100), unique=True, index=True, nullable=False)
    job_type = Column(String(50), nullable=False)  # 'interval' or 'cron'
    cron_expression = Column(String(100), nullable=True)
    interval_seconds = Column(Integer, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    last_run_time = Column(DateTime, nullable=True)
    next_run_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class JobExecutionHistory(Base):
    __tablename__ = "job_execution_history"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(100), index=True, nullable=False)
    status = Column(String(50), nullable=False)  # 'SUCCESS' or 'FAILED' or 'RUNNING'
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    correlation_id = Column(String(100), index=True, nullable=True)
    error_message = Column(Text, nullable=True)
