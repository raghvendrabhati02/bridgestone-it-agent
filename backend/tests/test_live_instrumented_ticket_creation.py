"""
tests/test_live_instrumented_ticket_creation.py
─────────────────────────────────────────────────────────────────────────────
Live end-to-end instrumented test for ServiceNow incident creation.
Traces:
ConversationService
↓
TicketOrchestrator
↓
ticket_service.create_ticket()
↓
ServiceNowService.create_incident()
↓
ServiceNowClient.create_incident()
↓
ServiceNowClient._safe_request()
↓
ServiceNowClient._execute_request()
"""

import sys
import logging
import uuid
from dotenv import load_dotenv

load_dotenv()

# Configure logger to output directly to stdout
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
root_logger.addHandler(handler)

import os
sys.path.insert(0, os.path.abspath("."))
from app.core.logging_context import correlation_id_ctx
from app.services.conversation_service import ConversationService, ConversationPhase


def run_live_trace():
    # 1. Generate request UUID correlation ID
    corr_id = f"corr-{uuid.uuid4().hex[:8]}"
    correlation_id_ctx.set(corr_id)

    print(f"\n==================== STARTING INSTRUMENTED TRACE ({corr_id}) ====================")

    service = ConversationService()
    
    # 2. Turn 1: User requests VPN help
    turn1 = service.handle_chat_turn(None, "VPN connection failure, please open a ticket", username="trace_user")
    session_id = turn1["session_id"]
    state = service._session_mgr.get(session_id)
    
    print(f"\n--- Turn 1 Result (Session ID: {session_id}, Phase: {state.phase}) ---")
    print(f"Action: {turn1.get('action')}, Ticket Created: {turn1.get('ticket_created')}, Ticket ID: {turn1.get('ticket_id')}")

    # 3. If in WAITING_TICKET_CONFIRMATION, send confirmation 'create'
    if state.phase == ConversationPhase.WAITING_TICKET_CONFIRMATION:
        print("\n--- Turn 2: User sends explicit confirmation 'create' ---")
        turn2 = service.handle_chat_turn(session_id, "create", username="trace_user")
        print(f"\n--- Turn 2 Result ---")
        print(f"Response text: {turn2.get('response', '').encode('ascii', 'replace').decode('ascii')}")
        print(f"Ticket Created: {turn2.get('ticket_created')}, Ticket ID: {turn2.get('ticket_id')}")
    
    print(f"\n==================== END INSTRUMENTED TRACE ({corr_id}) ====================\n")

if __name__ == "__main__":
    run_live_trace()
