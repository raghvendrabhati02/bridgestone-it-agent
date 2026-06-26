import json
import logging
import traceback
from datetime import datetime, timezone
from app.core.logging_context import get_context_dict

class JsonFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    Automatically merges values from the active async logging context.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }

        # Merge active async context dictionary values
        context_data = get_context_dict()
        log_data.update(context_data)

        # Merge extra attributes passed in log record (e.g. status_code, execution_time)
        standard_attrs = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "module", "msecs",
            "message", "msg", "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "thread", "threadName"
        }
        for k, v in record.__dict__.items():
            if k not in standard_attrs and not k.startswith("_"):
                log_data[k] = v

        # Inject exception traceback if present
        if record.exc_info:
            log_data["error_stack"] = "".join(traceback.format_exception(*record.exc_info))
            # Set the context-local error stack variable as well if not already set
            from app.core.logging_context import error_stack_ctx
            if not error_stack_ctx.get():
                error_stack_ctx.set(log_data["error_stack"])

        return json.dumps(log_data)

def setup_json_logging(level=logging.INFO):
    """
    Configures standard Python logging to output structured JSON records.
    Removes existing handlers and sets up a StreamHandler with JsonFormatter.
    """
    root_logger = logging.getLogger()
    
    # Remove existing handlers to avoid duplicate output
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Set root logger level
    root_logger.setLevel(level)

    # Create console handler with JsonFormatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JsonFormatter())
    
    root_logger.addHandler(console_handler)
    
    # Also explicitly configure the application logger
    app_logger = logging.getLogger("it-agent-backend")
    app_logger.setLevel(level)
    
    # Ensure it propagates to the root logger handlers
    app_logger.propagate = True
    
    app_logger.info("Structured JSON Logging initialized successfully.")
