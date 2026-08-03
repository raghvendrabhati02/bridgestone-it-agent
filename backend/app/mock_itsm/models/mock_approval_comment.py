from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database.base import Base

class MockApprovalComment(Base):
    __tablename__ = "mock_approval_comments"

    id = Column(Integer, primary_key=True, index=True)
    approval_id = Column(Integer, index=True, nullable=False)
    ticket_number = Column(String(50), index=True, nullable=False)
    author = Column(String(100), nullable=False)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
