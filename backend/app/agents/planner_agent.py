import logging

logger = logging.getLogger("it-agent-backend")

class PlannerAgent:
    def __init__(self):
        pass

    def generate_plan(self, intent: str, category: str, message: str, history: list[dict], current_status: str, tool_result: dict = None, approval_status: str = "PENDING") -> list[str]:
        """
        Generates planned next steps.
        Possible plan steps: ASK_QUESTION, RUN_TOOL, CREATE_TICKET, REQUEST_APPROVAL, EXECUTE_ACTION, CANCEL_WORKFLOW, RESOLVE_ISSUE
        """
        logger.info("PlannerAgent: Generating plan for intent: %s, category: %s, status: %s", intent, category, current_status)
        plan = []

        # 1. Handle Greetings / Small Talk / Identity
        if intent in ("GREETING", "IDENTITY", "SMALL_TALK"):
            plan.append("ASK_QUESTION")
            return plan

        # 2. Handle Approval responses
        if intent == "APPROVAL_RESPONSE":
            if approval_status == "APPROVED":
                plan.append("EXECUTE_ACTION")
            elif approval_status == "REJECTED":
                plan.append("CANCEL_WORKFLOW")
            else:
                # If no approval status is set but they answered yes/no, check message contents
                msg_lower = message.lower().strip()
                if any(kw in msg_lower for kw in ["yes", "approve", "proceed", "go ahead", "ok", "okay", "do it"]):
                    plan.append("EXECUTE_ACTION")
                else:
                    plan.append("CANCEL_WORKFLOW")
            return plan

        # 3. Handle Ticket Requests
        if intent == "TICKET_REQUEST":
            plan.append("CREATE_TICKET")
            return plan

        # 4. Handle Follow-up responses
        if intent == "FOLLOW_UP":
            msg_lower = message.lower().strip()
            # If resolved
            if any(kw in msg_lower for kw in ["resolved", "solved", "fixed", "working now", "working fine", "it works", "it's working"]):
                plan.append("RESOLVE_ISSUE")
            # If still not working
            elif any(kw in msg_lower for kw in ["still not working", "failed", "didn't help", "didn't work", "did not help", "did not work", "unsuccessful", "still broken"]):
                plan.append("CREATE_TICKET")
            else:
                # Default follow-up action is to check diagnostic results and continue troubleshooting
                self._plan_troubleshooting(category, tool_result, plan)
            return plan

        # 5. Handle General IT Issues
        if intent == "IT_ISSUE":
            self._plan_troubleshooting(category, tool_result, plan)
            return plan

        # Default fallback
        plan.append("ASK_QUESTION")
        return plan

    def _plan_troubleshooting(self, category: str, tool_result: dict, plan: list[str]):
        """
        Core troubleshooting planner logic. Decides between requesting approval, running more diagnostic steps, or escalating.
        """
        # If tool results exist, analyze them to see if we can recommend a corrective action
        if tool_result and isinstance(tool_result, dict):
            tool_data = tool_result.get("data", {})
            tool_name = tool_result.get("tool_name", "")
            
            # Case 1: VPN Access is disabled -> Request access restoration approval
            if tool_name == "vpn_tools" and tool_data.get("user_access") == "DISABLED":
                plan.append("REQUEST_APPROVAL")
                return
                
        # Default is to ask follow-up troubleshooting questions
        plan.append("ASK_QUESTION")
