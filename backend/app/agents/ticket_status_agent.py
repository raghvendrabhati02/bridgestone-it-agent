import logging


logger = logging.getLogger("it-agent-backend")


class TicketStatusAgent:
    """
    Detects whether a user message is a ticket-status inquiry.
    """

    STATUS_KEYWORDS = [
        "status",
        "ticket status",
        "progress",
        "update",
        "check ticket",
        "where is my ticket",
        "what's the status",
        "what is the status",
        "how is my ticket",
    ]

    def is_status_request(self, message: str) -> bool:
        msg = message.lower().strip()
        return any(keyword in msg for keyword in self.STATUS_KEYWORDS)