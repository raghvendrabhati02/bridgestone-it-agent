from sqlalchemy.orm import Session
from app.database.models.agent_trace import AgentTrace
from datetime import datetime

class TraceRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(
        self,
        session_id: str,
        agent_name: str,
        input_data: dict = None,
        output_data: dict = None
    ) -> AgentTrace:
        from app.core.logging_context import correlation_id_ctx
        trace = AgentTrace(
            session_id=session_id,
            agent_name=agent_name,
            input_data=input_data,
            output_data=output_data,
            correlation_id=correlation_id_ctx.get() or None,
            created_at=datetime.utcnow()
        )
        self.db.add(trace)
        self.db.commit()
        self.db.refresh(trace)
        return trace

    def get_all(self) -> list[AgentTrace]:
        return self.db.query(AgentTrace).order_by(AgentTrace.id.asc()).all()
