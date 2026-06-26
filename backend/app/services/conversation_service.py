import uuid
import logging
from app.services.knowledge_service import get_guide_content
from app.services.llm_service import generate_response
from app.services.rag_service import (
    load_knowledge_context,
    get_document_for_category
)

logger = logging.getLogger("it-agent-backend")

# In-memory storage cache for conversations (backed by DB)
conversations = {}

class ConversationState:
    def __init__(self, session_id: str, category: str, message: str):
        self.session_id = session_id
        self.category = category
        self.current_step = 0
        self.conversation_history = [{"sender": "user", "text": message}]
        self._status = "ACTIVE"  # ACTIVE, WAITING_FOR_CONFIRMATION, SOLVED, UNSOLVED, RESOLVED, TICKET_CREATED, AWAITING_APPROVAL
        self.steps = []
        self.approval_required = False
        self.approval_status = "PENDING"
        self.recommended_action = ""
        self.action_result = None
        self.tool_result = {}
        self.active_issue = ""
        self.active_ticket = ""
        self.active_request = ""
        self.conversation_goal = ""
        self.last_action = ""
        self.diagnostic_interview = None
        self.tool_chain = []
        self.hypothesis_tracker = []
        self.engineer_summary = None
        self.troubleshooting_iterations = 0
        self.troubleshooting_complete = False
        self.next_tool = None


    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, val: str):
        old_val = getattr(self, "_status", None)
        new_val = str(val).upper().strip()
        self._status = new_val
        if new_val == "RESOLVED" and old_val != "RESOLVED":
            try:
                from app.core.metrics import BUSINESS_TICKETS_RESOLVED_TOTAL
                BUSINESS_TICKETS_RESOLVED_TOTAL.inc()
            except Exception:
                pass

def detect_issue_change(current_category: str, latest_user_message: str) -> dict:
    """
    Detects if the user's latest message indicates a switch to a new issue category.
    """
    msg_lower = latest_user_message.lower().strip()
    
    # 1. Outlook checks
    outlook_keywords = ["outlook not opening", "outlook issue", "email issue"]
    if any(kw in msg_lower for kw in outlook_keywords):
        if current_category != "OUTLOOK":
            return {
                "issue_changed": True,
                "new_category": "OUTLOOK"
            }
            
    # 2. Software installation checks
    software_keywords = ["software installation", "unable to install software", "need software installation"]
    if any(kw in msg_lower for kw in software_keywords):
        if current_category != "SOFTWARE_INSTALLATION":
            return {
                "issue_changed": True,
                "new_category": "SOFTWARE_INSTALLATION"
            }
            
    # 3. Printer checks
    printer_keywords = ["printer not working"]
    if any(kw in msg_lower for kw in printer_keywords):
        if current_category != "PRINTER":
            return {
                "issue_changed": True,
                "new_category": "PRINTER"
            }
            
    return {
        "issue_changed": False,
        "new_category": None
    }

def generate_gemini_turn(state: ConversationState, user_message: str) -> str:
    """
    Calls RAG service to load reference context, compiles history,
    and queries Gemini to get the next diagnostic troubleshooting step.
    """
    context = load_knowledge_context(state.category)
    
    prompt = (
        "You are the Bridgestone IT support agent. Help the user troubleshoot their issue.\n"
        f"Issue Category: {state.category}\n\n"
    )
        
    prompt += "Conversation History:\n"
    for msg in state.conversation_history:
        sender = "Employee" if msg["sender"] == "user" else "IT Agent"
        prompt += f"{sender}: {msg['text']}\n"
        
    prompt += f"Employee's latest response: {user_message}\n"
    prompt += "Instructions:\n"
    prompt += "- Be a friendly, professional IT support engineer.\n"
    prompt += "- Keep your response under 3 sentences.\n"
    prompt += "- Ask ONE clear troubleshooting or diagnostic question to guide the user next.\n"
    
    res = generate_response(prompt, knowledge_context=context)
    if isinstance(res, dict) and "debug_error" in res:
        logger.warning("Gemini chat turn generation returned error: %s. Using local fallback.", res.get("debug_error"))
        return f"It looks like you're experiencing some trouble with {state.category}. Could you describe the symptoms you're seeing, or would you like me to raise a support ticket?"
    return res

def start_conversation(message: str, category: str) -> ConversationState:
    session_id = str(uuid.uuid4())
    state = ConversationState(session_id, category, message)
    conversations[session_id] = state
    
    # Generate the first response dynamically using Gemini
    first_question = generate_gemini_turn(state, message)
    state.steps = [first_question]
    state.conversation_history = [
        {"sender": "user", "text": message},
        {"sender": "agent", "text": first_question}
    ]
    
    # Persist session and initial turn to Database
    from app.database.session import get_db
    from app.database.repositories.conversation_repository import ConversationRepository
    try:
        with get_db() as db:
            repo = ConversationRepository(db)
            repo.save_session(
                session_id=state.session_id,
                category=state.category,
                current_step=state.current_step,
                status=state.status,

                approval_required=state.approval_required,
                approval_status=state.approval_status,

                recommended_action=state.recommended_action,

                action_result=state.action_result,
                tool_result=state.tool_result,

                active_ticket=state.active_ticket,
                active_issue=state.active_issue,
                active_request=state.active_request,
                conversation_goal=state.conversation_goal,
                last_action=state.last_action,
            )
            repo.save_turn(
                session_id=state.session_id,
                user_message=message,
                agent_response=first_question,
                category=state.category
            )
            logger.info("Conversation Service: Persisted initial session %s to database", state.session_id)
    except Exception as e:
        logger.error("Conversation Service: Failed to persist initial session to database: %s", e)
        
    logger.info("Conversation started: session_id=%s, category=%s", session_id, category)
    return state

def get_conversation(session_id: str) -> ConversationState | None:
    from app.core.metrics import REDIS_CACHE_HITS_TOTAL, REDIS_CACHE_MISSES_TOTAL, REDIS_SESSION_RESTORATIONS_TOTAL
    # 1. Try in-memory cache first
    if session_id in conversations:
        try:
            REDIS_CACHE_HITS_TOTAL.inc()
        except Exception:
            pass
        return conversations[session_id]
        
    try:
        REDIS_CACHE_MISSES_TOTAL.inc()
    except Exception:
        pass

    # 2. Try loading from database
    from app.database.session import get_db
    from app.database.repositories.conversation_repository import ConversationRepository
    try:
        with get_db() as db:
            repo = ConversationRepository(db)
            db_session = repo.get_session(session_id)
            if not db_session:
                return None
                
            turns = repo.get_turns(session_id)
            first_user_msg = turns[0].user_message if turns else "Hello"
            
            # Reconstruct ConversationState
            state = ConversationState(session_id, db_session.category, first_user_msg)
            state.current_step = db_session.current_step
            state._status = db_session.status
            state.approval_required = db_session.approval_required
            state.approval_status = db_session.approval_status
            state.recommended_action = db_session.recommended_action
            state.action_result = db_session.action_result
            state.tool_result = db_session.tool_result or {}

            state.active_ticket = db_session.active_ticket or ""
            state.active_issue = db_session.active_issue or ""
            state.active_request = db_session.active_request or ""
            state.conversation_goal = db_session.conversation_goal or ""
            state.last_action = db_session.last_action or ""
            
            # Reconstruct history
            history = []
            for t in turns:
                history.append({"sender": "user", "text": t.user_message})
                history.append({"sender": "agent", "text": t.agent_response})
            state.conversation_history = history
            
            conversations[session_id] = state
            try:
                REDIS_SESSION_RESTORATIONS_TOTAL.inc()
            except Exception:
                pass
            logger.info("Conversation Service: Restored session %s from database", session_id)
            return state
    except Exception as e:
        logger.error("Conversation Service: Error restoring conversation session %s from database: %s", session_id, e)
        return None

def process_message(session_id: str, message: str) -> dict:
    state = get_conversation(session_id)
    if not state:
        logger.warning("Conversation state not found for session_id: %s. Starting new.", session_id)
        state = start_conversation(message, "GENERAL")
        
    solved = False
    ticket_required = False
    ticket_details = None
    actions = None
    
    # Handle confirmation check
    if state.status in ("WAITING_FOR_CONFIRMATION", "TROUBLESHOOTING_COMPLETE", "AWAITING_CONFIRMATION"):
        cleaned_msg = message.strip().upper()
        if cleaned_msg in ("SOLVED", "YES"):
            state.status = "RESOLVED"
            bot_text = "Glad I could help."
            solved = True
        else:
            state.status = "TICKET_CREATED"
            # Extract issue description (user's first query)
            issue_desc = state.conversation_history[0]["text"] if state.conversation_history else "IT Support Issue"
            from app.services.ticket_service import create_ticket
            ticket_details = create_ticket(state.category, issue_desc)
            bot_text = f"I've created support ticket {ticket_details['ticket_id']} assigned to {ticket_details['assigned_team']}."
            ticket_required = True
    else:
        # Handle active steps
        state.current_step += 1
        
        if state.current_step < 3: # Let the conversation run for up to 3 diagnostic questions
            bot_text = generate_gemini_turn(state, message)
        else:
            state.status = "AWAITING_CONFIRMATION"
            bot_text = "Did this solve your issue?"
            actions = ["SOLVED", "NOT_SOLVED"]

    state.conversation_history.append({"sender": "user", "text": message})
    state.conversation_history.append({"sender": "agent", "text": bot_text})

    # Save to Database
    from app.database.session import get_db
    from app.database.repositories.conversation_repository import ConversationRepository
    try:
        with get_db() as db:
            repo = ConversationRepository(db)
            repo.save_session(
                session_id=state.session_id,
                category=state.category,
                current_step=state.current_step,
                status=state.status,
                approval_required=state.approval_required,
                approval_status=state.approval_status,
                recommended_action=state.recommended_action,
                action_result=state.action_result,
                tool_result=state.tool_result,

                active_ticket=state.active_ticket,
                active_issue=state.active_issue,
                active_request=state.active_request,
                conversation_goal=state.conversation_goal,
                last_action=state.last_action,
            )
            repo.save_turn(
                session_id=state.session_id,
                user_message=message,
                agent_response=bot_text,
                category=state.category
            )
            logger.info("Conversation Service: Persisted session %s from process_message to database", state.session_id)
    except Exception as e:
        logger.error("Conversation Service: Failed to persist process_message turn to database: %s", e)

    response_payload = {
        "session_id": state.session_id,
        "category": state.category,
        "source": get_document_for_category(state.category),
        "context_used": get_document_for_category(state.category) != "N/A",
        "question": bot_text,
        "response": bot_text,
        "status": state.status,
        "solved": solved,
        "ticket_required": ticket_required,
        "history_length": len(state.conversation_history)
    }
    if ticket_details:
        response_payload["ticket"] = ticket_details
    if actions:
        response_payload["actions"] = actions
        response_payload["message"] = bot_text
        
    return response_payload

def handle_chat_turn(session_id: str | None, message: str, username: str = None, user_role: str = None) -> dict:
    """
    Core conversation loop integrating intent detection, conversation history memory,
    grounded knowledge context retrieval, response generation, and structured Decision Agent analysis.
    """
    from app.services.intent_service import detect_intent
    from app.services.decision_service import analyze_conversation
    from app.services.ticket_service import create_ticket

    if not session_id:
        # Start a new conversation state
        session_id = str(uuid.uuid4())
        category = detect_intent(message)
        if isinstance(category, dict) and "debug_error" in category:
            return category
        state = ConversationState(session_id, category, message)
        state.conversation_history = []  # Clear default to avoid duplicate prompt inputs
        conversations[session_id] = state
    else:
        state = get_conversation(session_id)
        if not state:
            session_id = str(uuid.uuid4())
            category = detect_intent(message)
            if isinstance(category, dict) and "debug_error" in category:
                return category
            state = ConversationState(session_id, category, message)
            state.conversation_history = []
            conversations[session_id] = state
        else:
            detected_category = detect_intent(message)
            if isinstance(detected_category, dict) and "debug_error" in detected_category:
                return detected_category
            if detected_category != "GENERAL" and detected_category != state.category:
                old_category = state.category
                logger.info("Category switch detected for session_id %s: %s -> %s", session_id, old_category, detected_category)
                state.status = "RESOLVED"
                
                # Reset context and start a new state under the same session_id
                state = ConversationState(session_id, detected_category, message)
                state.conversation_history = []
                conversations[session_id] = state

    # Check if session status is AWAITING_APPROVAL, and user approved/rejected
    if state and state.status == "AWAITING_APPROVAL":
        msg_cleaned = message.lower().strip()
        if any(kw in msg_cleaned for kw in ["yes", "approve", "proceed", "go ahead", "ok", "okay", "do it"]):
            state.approval_status = "APPROVED"
            try:
                from app.services.audit_service import log_approval
                log_approval(
                    session_id=state.session_id,
                    recommended_action=state.recommended_action,
                    approval_status="APPROVED"
                )
            except Exception as e:
                logger.error("Conversation Service: Failed to log approval: %s", e)
        elif any(kw in msg_cleaned for kw in ["no", "cancel", "reject", "stop", "abort"]):
            state.approval_status = "REJECTED"
            try:
                from app.services.audit_service import log_approval
                log_approval(
                    session_id=state.session_id,
                    recommended_action=state.recommended_action,
                    approval_status="REJECTED"
                )
            except Exception as e:
                logger.error("Conversation Service: Failed to log approval: %s", e)

    # Invoke the LangGraph workflow
    from app.graph.graph import app_graph

    # ── Security: only forward live approval context when the session is
    # genuinely AWAITING_APPROVAL.  If the previous turn ended with
    # ACCESS_DENIED, state.status is "ACTIVE" (not "AWAITING_APPROVAL"),
    # so we reset both fields to neutral defaults.  This prevents a stale
    # recommended_action / approval_status from being injected into the
    # graph and allowing the LLM to re-trigger a privileged action on
    # behalf of an unauthorized user.
    _session_awaiting = getattr(state, "status", "ACTIVE") == "AWAITING_APPROVAL"
    _fwd_approval_status     = getattr(state, "approval_status", "PENDING") if _session_awaiting else "PENDING"
    _fwd_recommended_action  = getattr(state, "recommended_action", "")    if _session_awaiting else ""
    _fwd_approval_required   = getattr(state, "approval_required", False)   if _session_awaiting else False

    initial_state = {
        "session_id": state.session_id,
        "user_message": message,
        "category": state.category,

        "active_issue": getattr(state, "active_issue", ""),
        "active_ticket": getattr(state, "active_ticket", ""),
        "active_request": getattr(state, "active_request", ""),
        "conversation_goal": getattr(state, "conversation_goal", ""),
        "last_action": getattr(state, "last_action", ""),

        "knowledge_context": "",
        "tool_result": getattr(state, "tool_result", {}),
        "plan": {},               # populated by planner_node during troubleshooting
        "root_cause_analysis": None,  # populated by root_cause_node
        "reflection": None,       # populated by reflection_node
        "memory": None,           # populated by memory_node
        "decision": "",
        "decision_response": "",  # populated by decision/conversation/ticket_status nodes
        "route": "",              # populated by context_router_node
        "ticket": {},
        "assigned_team": "",
        "notifications": [],
        "sla": {},
        "approval_required":  _fwd_approval_required,
        "approval_status":    _fwd_approval_status,
        "recommended_action": _fwd_recommended_action,
        "action_result": getattr(state, "action_result", None),
        "username": username,
        "user_role": user_role or "EMPLOYEE",
        "diagnostic_interview": getattr(state, "diagnostic_interview", None),
        "tool_chain": getattr(state, "tool_chain", []),
        "hypothesis_tracker": getattr(state, "hypothesis_tracker", []),
        "engineer_summary": getattr(state, "engineer_summary", None),
        "troubleshooting_iterations": getattr(state, "troubleshooting_iterations", 0),
        "troubleshooting_complete": getattr(state, "troubleshooting_complete", False),
        "next_tool": getattr(state, "next_tool", None),
    }


    logger.info(
        "ConversationService: Invoking graph with initial_state keys=%s, "
        "active_ticket='%s', category='%s'",
        list(initial_state.keys()),
        initial_state.get("active_ticket"),
        initial_state.get("category"),
    )
    logger.info("=== START GRAPH ===")
    try:
        final_state = app_graph.invoke(initial_state)
    except Exception as graph_err:
        logger.error(
            "ConversationService: Graph invocation failed with unhandled exception: %s",
            graph_err,
            exc_info=True,
        )
        # Return a safe fallback state so the API can still respond instead of 500-ing
        final_state = {
            **initial_state,
            "decision": "ASK_MORE_INFO",
            "decision_response": (
                "I encountered an internal error while processing your request. "
                "Please try again in a moment."
            ),
        }

    logger.info(
        "ConversationService: Graph complete — decision='%s', active_ticket='%s'",
        final_state.get("decision"),
        final_state.get("active_ticket"),
    )

    state.active_issue = final_state.get(
        "active_issue",
        getattr(state, "active_issue", "")
    )

    state.active_ticket = final_state.get(
        "active_ticket",
        getattr(state, "active_ticket", "")
    )

    state.active_request = final_state.get(
        "active_request",
        getattr(state, "active_request", "")
    )

    state.conversation_goal = final_state.get(
        "conversation_goal",
        getattr(state, "conversation_goal", "")
    )

    state.last_action = final_state.get(
        "last_action",
        getattr(state, "last_action", "")
    )
    logger.info("=== GRAPH COMPLETE ===")
    
    # Update category if modified during graph execution
    state.category = final_state.get("category", state.category)
    
    # Persist graph approval states to session memory.
    # ── Security: when the graph returned ACCESS_DENIED, wipe all approval
    # context from the session object so it cannot be replayed on the next
    # turn.  For every other outcome we copy faithfully from final_state.
    _final_action = final_state.get("decision", "")
    if _final_action == "ACCESS_DENIED":
        logger.warning(
            "ConversationService: ACCESS_DENIED — clearing approval context "
            "for session '%s' (user='%s', role='%s').",
            state.session_id,
            username,
            user_role,
        )
        state.approval_status    = "ACCESS_DENIED"  # sentinel — not PENDING
        state.recommended_action = ""               # wipe stale action name
        state.approval_required  = False
    else:
        state.approval_required  = final_state.get("approval_required", False)
        state.approval_status    = final_state.get("approval_status", "PENDING")
        state.recommended_action = final_state.get("recommended_action", "")
    state.action_result = final_state.get("action_result")
    state.tool_result   = final_state.get("tool_result", {})
    state.diagnostic_interview = final_state.get("diagnostic_interview")
    state.tool_chain = final_state.get("tool_chain", [])
    state.hypothesis_tracker = final_state.get("hypothesis_tracker", [])
    state.engineer_summary = final_state.get("engineer_summary")
    state.troubleshooting_iterations = final_state.get("troubleshooting_iterations", 0)
    state.troubleshooting_complete = final_state.get("troubleshooting_complete", False)
    state.next_tool = final_state.get("next_tool")
    # Store reflection for subsequent turns (available for follow-up reasoning)

    if not hasattr(state, "last_reflection"):
        state.last_reflection = None
    state.last_reflection = final_state.get("reflection") or state.last_reflection

    # ── Always extract context-manager fields from final_state ───────────────
    # These are updated by ticket_node, context_router_node, etc.
    # We must read them back BEFORE save_session() is called.
    _fs_active_ticket = final_state.get("active_ticket") or ""
    _fs_active_issue  = final_state.get("active_issue")  or ""
    _fs_last_action   = final_state.get("last_action")   or ""

    # Prefer graph output; fall back to session memory so existing values are never erased
    if _fs_active_ticket:
        state.active_ticket = _fs_active_ticket
    if _fs_active_issue:
        state.active_issue = _fs_active_issue
    if _fs_last_action:
        state.last_action = _fs_last_action

    logger.info(
        "ConversationService: Post-graph context — active_ticket='%s', "
        "active_issue='%s', last_action='%s'",
        state.active_ticket,
        state.active_issue,
        state.last_action,
    )

    action = final_state.get("decision", "ASK_MORE_INFO")
    decision_response = final_state.get("decision_response")
    
    # Process designated Decision Agent action
    ticket_created = False
    ticket_id = None
    ticket_details = None
    
    if decision_response:
        bot_text = decision_response
        if action == "TICKET_STATUS":
            # Ticket status query — just relay the response, keep state active
            state.status = "ACTIVE"
        elif action in ("TICKET_CREATED", "CREATE_TICKET"):
            # Ticket was just created — ticket_node now returns TICKET_CREATED
            state.status = "TICKET_CREATED"
            ticket_details = final_state.get("ticket")
            ticket_created = True
            ticket_id = ticket_details.get("ticket_id") if ticket_details else None
            # Ensure active_ticket is set when graph propagation succeeded
            if ticket_id and not state.active_ticket:
                state.active_ticket = ticket_id
                logger.info(
                    "ConversationService: Set active_ticket=%s from TICKET_CREATED response",
                    ticket_id,
                )
        elif action in ("WAIT_FOR_APPROVAL", "REQUEST_APPROVAL"):
            state.status = "AWAITING_APPROVAL"
        elif action == "EXECUTE_ACTION":
            state.status = "RESOLVED"
        elif action == "REJECTED":
            state.status = "RESOLVED"
        else:
            state.status = "ACTIVE"
    else:
        # No decision_response from the multi-agent chain — build from reflection if available
        reflection = final_state.get("reflection")
        if action == "RESOLVED":
            bot_text = "I'm glad your issue has been resolved! Feel free to reach out if anything else comes up."
            state.status = "RESOLVED"
        elif action == "CREATE_TICKET":
            obs_text = ""
            if reflection and reflection.get("observations"):
                obs_text = f" {reflection['observations'][0]}"
            bot_text = (
                f"The diagnostics indicate this issue needs the IT team's attention.{obs_text} "
                f"I'm creating a support ticket now and the appropriate team will follow up with you shortly."
            )
            state.status = "TICKET_CREATED"
            ticket_details = final_state.get("ticket")
            ticket_created = True
            ticket_id = ticket_details.get("ticket_id") if ticket_details else None
        elif action in ("RECOMMEND_ACTION", "WAIT_FOR_APPROVAL", "REQUEST_APPROVAL"):
            # Build a reflection-aware approval request
            recommended_action = final_state.get("recommended_action", "")
            hyp_text = ""
            if reflection and reflection.get("hypotheses"):
                hyp_text = f" Based on the analysis, {reflection['hypotheses'][0].lower().rstrip('.')}."
            obs_text = ""
            if reflection and reflection.get("observations"):
                for obs in reflection.get("observations", []):
                    if "disabled" in obs.lower() or "denied" in obs.lower() or "offline" in obs.lower():
                        obs_text = f" I found that {obs.lower()}"
                        break
            if recommended_action == "VPN_ACCESS_RESTORATION":
                bot_text = (
                    f"I checked your VPN settings and the corporate gateway.{obs_text}{hyp_text} "
                    f"I can submit an access restoration request to re-enable your account. Would you like me to proceed?"
                )
            elif recommended_action == "SOFTWARE_INSTALLATION":
                bot_text = (
                    f"I've verified the software and your device permissions.{obs_text}{hyp_text} "
                    f"I can submit an installation request on your behalf. Shall I go ahead?"
                )
            else:
                bot_text = (
                    f"Based on the diagnostic results{obs_text}, I recommend a corrective action.{hyp_text} "
                    f"Shall I proceed with the recommended fix?"
                )
            state.status = "AWAITING_APPROVAL"
        elif action == "EXECUTE_ACTION":
            bot_text = "Your request has been submitted successfully. The IT team will process it and update you shortly."
            state.status = "RESOLVED"
        elif action == "REJECTED":
            bot_text = "Understood — I've cancelled the request. Let me know if you'd like to try a different approach or need help with anything else."
            state.status = "RESOLVED"
        else:
            # action == "ASK_MORE_INFO" -- use reflection to generate a useful response
            state.status = "ACTIVE"
            if reflection and (reflection.get("observations") or reflection.get("findings")):
                # Use reflection data to generate a natural question instead of generic fallback
                from app.agents.response_agent import ResponseAgent
                _resp_agent = ResponseAgent()
                bot_text = _resp_agent.generate_response(
                    user_message=message,
                    history=state.conversation_history,
                    plan=["ASK_QUESTION"],
                    reasoning=reflection,
                    category=state.category,
                )
            else:
                # Truly no diagnostic data yet -- use Gemini for a warm opening question
                bot_text = generate_gemini_turn(state, message)
                if isinstance(bot_text, dict) and "debug_error" in bot_text:
                    return bot_text
            
    # Append user query and agent reply to database history
    state.conversation_history.append({"sender": "user", "text": message})
    state.conversation_history.append({"sender": "agent", "text": bot_text})
    
    # Save session and turn to database
    from app.database.session import get_db
    from app.database.repositories.conversation_repository import ConversationRepository
    try:
        with get_db() as db:
            repo = ConversationRepository(db)
            repo.save_session(
                session_id=state.session_id,
                category=state.category,
                current_step=state.current_step,
                status=state.status,
                approval_required=state.approval_required,
                approval_status=state.approval_status,
                recommended_action=state.recommended_action,
                action_result=state.action_result,
                tool_result=state.tool_result,

                active_ticket=state.active_ticket,
                active_issue=state.active_issue,
                active_request=state.active_request,
                conversation_goal=state.conversation_goal,
                last_action=state.last_action,
            )
            repo.save_turn(
                session_id=state.session_id,
                user_message=message,
                agent_response=bot_text,
                category=state.category
            )
            logger.info("Conversation Service: Persisted session %s from handle_chat_turn to database", state.session_id)
    except Exception as e:
        logger.error("Conversation Service: Failed to persist handle_chat_turn to database: %s", e)

    logger.info("Decision Agent turn: session_id=%s, action=%s, ticket=%s", state.session_id, action, ticket_id)
    
    # Log Audit record in Audit Logging Framework
    try:
        from app.services.audit_service import log_audit
        log_audit(
            session_id=state.session_id,
            user_message=message,
            category=state.category,
            decision=action,
            approval_status=state.approval_status,
            recommended_action=state.recommended_action,
            action_result=state.action_result,
            ticket_id=ticket_id,
            servicenow_id=ticket_details.get("servicenow_id") if ticket_details else (state.action_result.get("servicenow_id") if state.action_result else None)
        )
    except Exception as e:
        logger.error("Conversation Service: Failed to log turn audit log: %s", e)
        
    return {
        "session_id": state.session_id,
        "category": state.category,
        "action": action,
        "response": bot_text,
        "history_length": len(state.conversation_history),
        "ticket_created": ticket_created,
        "ticket_id": ticket_id,
        "servicenow_id": ticket_details.get("servicenow_id") if ticket_details else None,
        "assigned_team": ticket_details.get("assigned_team") if ticket_details else None,
        "priority": ticket_details.get("priority") if ticket_details else None,
        "sla_hours": ticket_details.get("sla_hours") if ticket_details else None,
        "notifications_created": True if ticket_created else False,
        "ticket": ticket_details,
        "source": get_document_for_category(state.category),
        "context_used": get_document_for_category(state.category) != "N/A",
        "tool_result": state.tool_result,
        "approval_required": state.approval_required,
        "approval_status": state.approval_status,
        "recommended_action": state.recommended_action,
        "action_result": state.action_result
    }
