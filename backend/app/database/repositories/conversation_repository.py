from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models.session import SessionModel
from app.database.models.conversation import Conversation


class ConversationRepository:
    """
    Repository responsible for persisting and retrieving
    conversation sessions and chat history.
    """

    def __init__(self, db: Session):
        self.db = db

    def save_session(
        self,
        session_id: str,
        category: str = "GENERAL",
        current_step: int = 0,
        status: str = "ACTIVE",
        approval_required: bool = False,
        approval_status: str = "PENDING",
        recommended_action: str = "",
        action_result: Optional[dict] = None,
        tool_result: Optional[dict] = None,
        active_ticket: str = "",
        active_issue: str = "",
        active_request: str = "",
        conversation_goal: str = "",
        last_action: str = "",
    ) -> SessionModel:
        """
        Create or update a conversation session.
        """

        session_record = (
            self.db.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .first()
        )

        if not session_record:
            session_record = SessionModel(session_id=session_id)
            self.db.add(session_record)

        # Core session state
        session_record.category = category
        session_record.current_step = current_step
        session_record.status = status

        # Approval workflow
        session_record.approval_required = approval_required
        session_record.approval_status = approval_status
        session_record.recommended_action = recommended_action

        # Tool / Action results
        session_record.action_result = action_result
        session_record.tool_result = tool_result

        # Context Manager fields
        session_record.active_ticket = active_ticket
        session_record.active_issue = active_issue
        session_record.active_request = active_request
        session_record.conversation_goal = conversation_goal
        session_record.last_action = last_action

        self.db.commit()
        self.db.refresh(session_record)

        return session_record

    def get_session(self, session_id: str) -> Optional[SessionModel]:
        """
        Retrieve a session by ID.
        """

        return (
            self.db.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .first()
        )

    def save_turn(
        self,
        session_id: str,
        user_message: str,
        agent_response: str,
        category: str,
    ) -> Conversation:
        """
        Persist a single conversation turn.
        """

        turn = Conversation(
            session_id=session_id,
            user_message=user_message,
            agent_response=agent_response,
            category=category,
            created_at=datetime.utcnow(),
        )

        self.db.add(turn)
        self.db.commit()
        self.db.refresh(turn)

        return turn

    def get_turns(self, session_id: str) -> list[Conversation]:
        """
        Retrieve all conversation turns for a session.
        """

        return (
            self.db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.id.asc())
            .all()
        )