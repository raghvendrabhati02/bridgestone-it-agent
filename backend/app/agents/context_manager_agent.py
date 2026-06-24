class ContextManagerAgent:

    def update_context(
        self,
        state,
        category=None,
        action=None,
        ticket_id=None,
        request_id=None
    ):

        if category:
            state["active_issue"] = category

        if ticket_id:
            state["active_ticket"] = ticket_id

        if request_id:
            state["active_request"] = request_id

        if action:
            state["last_action"] = action

        return state