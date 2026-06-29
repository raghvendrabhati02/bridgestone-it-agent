import os
import sys

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Inject mock before importing backend app
import mock_gemini

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.services.conversation_service import handle_chat_turn

def verify_conversation_quality():
    print("Running verify_conversation_quality.py...")
    failures = []

    def check(name, condition, msg):
        if condition:
            print(f"  [\u2705 PASS] {name}: {msg}")
        else:
            print(f"  [\u274c FAIL] {name}: {msg}")
            failures.append(name)

    try:
        # Scenario 1: Standard VPN timeout diagnostic check
        res = handle_chat_turn(
            session_id="sess-quality-01",
            message="My VPN is timing out on gateway Pune office",
            user_role="EMPLOYEE",
            username="employee"
        )
        
        reply = res.get("response", "")
        print(f"  Received reply: '{reply}'")
        
        # 1. Assert professional tone
        check(
            "Corporate Greeting / Tone present",
            any(w in reply.lower() for w in ["help", "assist", "support", "thank", "resolve", "bridgestone"]),
            "The assistant reply does not sound like a professional support desk agent."
        )
        
        # 2. Check for lack of development comments/placeholders in text
        placeholders = ["todo", "placeholder", "mock", "dummy", "test", "draft", "comment here"]
        has_placeholder = any(p in reply.lower() for p in placeholders)
        check(
            "No Development Placeholders in output",
            not has_placeholder,
            f"The assistant reply contains placeholder terminology: {[p for p in placeholders if p in reply.lower()]}."
        )

        # 3. Check message cleanliness
        check(
            "Message contains valid length",
            len(reply) > 10,
            f"Reply too short: length {len(reply)}"
        )

    except Exception as e:
        print(f"  [\u274c FAIL] Conversation quality crash: {e}")
        failures.append("Conversation quality crash")

    if failures:
        print(f"[FAIL] verify_conversation_quality.py failed with checks: {failures}")
        sys.exit(1)
    else:
        print("[PASS] verify_conversation_quality.py successfully passed all checks!")
        sys.exit(0)

if __name__ == "__main__":
    verify_conversation_quality()
