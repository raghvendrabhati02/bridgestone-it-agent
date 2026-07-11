"""
Verify conversation_persistence functionality.
"""
import uuid
import app.services.conversation_persistence as persistence
from app.services.conversation_state import ConversationContext, ConversationStateEnum
from app.services.conversation_service import ConversationState

def test_persistence_flow():
    session_id = str(uuid.uuid4())

    # 1. Test cache setters / getters
    state_mock = ConversationState(session_id, "VPN", "hello")
    state_mock.status = "ACTIVE"
    state_mock.current_step = 2

    persistence.cache_set(session_id, state_mock)
    cached = persistence.cache_get(session_id)
    assert cached is state_mock
    print("Cache GET/SET: OK")

    # 2. Test saving and retrieving session (via ConversationState model)
    persistence.save_session(session_id, state_mock)
    data = persistence.get_session_data(session_id)
    assert data is not None
    assert data["session_id"] == session_id
    assert data["category"] == "VPN"
    assert data["current_step"] == 2
    assert data["status"] == "ACTIVE"
    print("Save/Get Session (ConversationState): OK")

    # 3. Test saving and retrieving session (via ConversationContext model)
    session_id_ctx = str(uuid.uuid4())
    ctx = ConversationContext(conversation_id=session_id_ctx, state=ConversationStateEnum.UNDERSTANDING, category="OUTLOOK", current_step=3)
    persistence.save_session(session_id_ctx, ctx)
    data_ctx = persistence.get_session_data(session_id_ctx)
    assert data_ctx is not None
    assert data_ctx["session_id"] == session_id_ctx
    assert data_ctx["category"] == "OUTLOOK"
    assert data_ctx["current_step"] == 3
    assert data_ctx["status"] == "UNDERSTANDING"
    print("Save/Get Session (ConversationContext): OK")

    # 4. Test save_turn and get_turns
    persistence.save_turn(session_id, "user msg 1", "agent reply 1", "VPN")
    persistence.save_turn(session_id, "user msg 2", "agent reply 2", "VPN")

    turns = persistence.get_turns_data(session_id)
    assert len(turns) == 2
    assert turns[0]["user_message"] == "user msg 1"
    assert turns[0]["agent_response"] == "agent reply 1"
    assert turns[0]["category"] == "VPN"
    print("Save/Get Turns: OK")

    # Clean cache
    persistence.cache_remove(session_id)
    assert persistence.cache_get(session_id) is None
    print("Cache REMOVE: OK")

    print("\nAll checks passed.")

if __name__ == "__main__":
    test_persistence_flow()
