"""
Verify conversation_memory functionality.
"""
import uuid
import app.services.conversation_persistence as persistence
import app.services.conversation_memory as memory
from app.services.conversation_service import ConversationState

session_id = str(uuid.uuid4())

# 1. Setup session in cache
state_mock = ConversationState(session_id, "VPN", "initial msg")
state_mock.conversation_history = [
    {"sender": "user", "text": "initial msg"}
]
persistence.cache_set(session_id, state_mock)

# 2. Retrieve history
h1 = memory.get_history(session_id)
assert len(h1) == 1
assert h1[0]["sender"] == "user"
assert h1[0]["text"] == "initial msg"
print("get_history: OK")

# 3. Append single message
memory.append_message(session_id, "agent", "hello how can I help?")
h2 = memory.get_history(session_id)
assert len(h2) == 2
assert h2[1]["sender"] == "agent"
assert h2[1]["text"] == "hello how can I help?"
print("append_message: OK")

# 4. Trim history
t1 = memory.get_trimmed_history(session_id, 1)
assert len(t1) == 1
assert t1[0]["sender"] == "agent"

t2 = memory.get_trimmed_history(session_id, 5)
assert len(t2) == 2
print("get_trimmed_history: OK")

# 5. Format for orchestrator
f = memory.format_for_orchestrator(session_id)
assert len(f) == 2
assert f[0]["role"] == "user"
assert f[1]["role"] == "model"
assert f[1]["text"] == "hello how can I help?"
print("format_for_orchestrator: OK")

# 6. Append turn pair and persist
# Clear cache first to test pure DB writes and reads
persistence.cache_remove(session_id)

# Save two complete turn pairs to DB
memory.append_turn_pair(session_id, "initial msg", "hello how can I help?", "VPN")
memory.append_turn_pair(session_id, "i need vs code", "submitting request", "SOFTWARE_INSTALLATION")

# Re-read from cache (which was populated by the appends)
h3 = memory.get_history(session_id)
assert len(h3) == 4
assert h3[0]["text"] == "initial msg"
assert h3[1]["text"] == "hello how can I help?"
assert h3[2]["text"] == "i need vs code"
assert h3[3]["text"] == "submitting request"

# Now verify SQL save and database-only reconstruction by clearing cache
persistence.cache_remove(session_id)
h_db = memory.get_history(session_id)
assert len(h_db) == 4  # DB turns reconstructed correctly
assert h_db[0]["text"] == "initial msg"
assert h_db[2]["text"] == "i need vs code"
print("append_turn_pair + DB verify: OK")

print("\nAll memory checks passed.")
