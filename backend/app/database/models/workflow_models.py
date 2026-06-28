from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float
from datetime import datetime
from app.database.base import Base

class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(50), index=True, nullable=False)
    author = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False, nullable=False) # True = Work Note, False = Customer Comment
    correlation_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    edited_history = Column(Text, nullable=True) # JSON list of edits if updated

class AssignmentHistory(Base):
    __tablename__ = "assignment_history"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(50), index=True, nullable=False)
    assigned_group = Column(String(100), nullable=True)
    assigned_engineer = Column(String(100), nullable=True)
    assigned_by = Column(String(100), nullable=True)
    assigned_time = Column(DateTime, default=datetime.utcnow)
    reason = Column(Text, nullable=True)
    previous_engineer = Column(String(100), nullable=True)
    new_engineer = Column(String(100), nullable=True)
    correlation_id = Column(String(100), nullable=True)

class TicketTimeline(Base):
    __tablename__ = "ticket_timeline"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(50), index=True, nullable=False)
    event_type = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    correlation_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DuplicateRelationship(Base):
    __tablename__ = "duplicate_relationships"

    id = Column(Integer, primary_key=True, index=True)
    source_ticket_id = Column(String(50), index=True, nullable=False)
    target_ticket_id = Column(String(50), index=True, nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False) # CONFIRMED, DISMISSED, PENDING
    created_at = Column(DateTime, default=datetime.utcnow)

class IncidentCluster(Base):
    __tablename__ = "incident_clusters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    known_fix = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CSATSurvey(Base):
    __tablename__ = "csat_surveys"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(50), index=True, nullable=False, unique=True)
    rating = Column(Integer, nullable=False) # 1-5
    feedback = Column(Text, nullable=True)
    response_time_rating = Column(Integer, nullable=True) # 1-5
    resolution_quality_rating = Column(Integer, nullable=True) # 1-5
    would_recommend = Column(Boolean, default=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class KnowledgeDraft(Base):
    __tablename__ = "knowledge_drafts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    problem = Column(Text, nullable=True)
    environment = Column(Text, nullable=True)
    symptoms = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    workaround = Column(Text, nullable=True)
    tags = Column(String(200), nullable=True) # comma separated
    category = Column(String(100), nullable=True)
    affected_systems = Column(String(200), nullable=True)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="DRAFT") # DRAFT, PUBLISHED
    source_ticket_id = Column(String(50), nullable=True)
