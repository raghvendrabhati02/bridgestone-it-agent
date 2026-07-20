import contextvars

# Context variables to track observability parameters across async threads
request_id_ctx = contextvars.ContextVar("request_id", default="")
correlation_id_ctx = contextvars.ContextVar("correlation_id", default="")
session_id_ctx = contextvars.ContextVar("session_id", default="")
user_ctx = contextvars.ContextVar("user", default="anonymous")
role_ctx = contextvars.ContextVar("role", default="anonymous")
endpoint_ctx = contextvars.ContextVar("endpoint", default="")
ai_decision_ctx = contextvars.ContextVar("ai_decision", default="")
tool_executed_ctx = contextvars.ContextVar("tool_executed", default="")
ticket_id_ctx = contextvars.ContextVar("ticket_id", default="")
error_stack_ctx = contextvars.ContextVar("error_stack", default="")
turn_start_time_ctx = contextvars.ContextVar("turn_start_time", default=0.0)

def clear_logging_context():
    """
    Resets all request-scoped context variables to their default values.
    Should be called at the beginning of each HTTP request/job execution.
    """
    request_id_ctx.set("")
    correlation_id_ctx.set("")
    session_id_ctx.set("")
    user_ctx.set("anonymous")
    role_ctx.set("anonymous")
    endpoint_ctx.set("")
    ai_decision_ctx.set("")
    tool_executed_ctx.set("")
    ticket_id_ctx.set("")
    error_stack_ctx.set("")
    turn_start_time_ctx.set(0.0)

def get_context_dict() -> dict:
    """
    Returns a dictionary of all active context variable values.
    """
    return {
        "request_id": request_id_ctx.get(),
        "correlation_id": correlation_id_ctx.get(),
        "session_id": session_id_ctx.get(),
        "user": user_ctx.get(),
        "role": role_ctx.get(),
        "endpoint": endpoint_ctx.get(),
        "ai_decision": ai_decision_ctx.get(),
        "tool_executed": tool_executed_ctx.get(),
        "ticket_id": ticket_id_ctx.get(),
        "error_stack": error_stack_ctx.get()
    }
