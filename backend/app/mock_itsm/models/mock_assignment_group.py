from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.database.base import Base

class MockAssignmentGroup(Base):
    __tablename__ = "mock_assignment_groups"

    id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    lead_engineer = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
