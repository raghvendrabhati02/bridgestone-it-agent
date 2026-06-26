from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database.base import Base


class RbacAuditLog(Base):
    """
    Dedicated audit table for enterprise RBAC and lifecycle events.

    Fields
    ------
    audit_id   : auto PK
    timestamp  : UTC datetime of the event
    user       : username performing the action
    role       : role of that user at the time
    action     : what action was attempted / performed  (e.g. 'close_ticket')
    ticket_id  : affected ticket (nullable for non-ticket actions)
    old_state  : previous lifecycle state (nullable)
    new_state  : resulting lifecycle state (nullable)
    details    : JSON-serialised extra context (nullable)
    """

    __tablename__ = "rbac_audit_logs"

    audit_id  = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    user      = Column(String(100), nullable=False, index=True)
    role      = Column(String(50),  nullable=False)
    action    = Column(String(100), nullable=False, index=True)
    ticket_id = Column(String(50),  nullable=True,  index=True)
    old_state = Column(String(50),  nullable=True)
    new_state = Column(String(50),  nullable=True)
    details   = Column(Text,        nullable=True)
