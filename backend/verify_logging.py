import sys
import os
import unittest
import logging
import json
import io
from contextlib import redirect_stderr

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.logging_context import request_id_ctx, correlation_id_ctx, session_id_ctx, user_ctx, role_ctx, clear_logging_context
from app.core.json_logger import JsonFormatter

class TestJSONLogging(unittest.TestCase):
    def test_json_formatter(self):
        """Verifies that the JsonFormatter correctly serializes logs to JSON with context vars."""
        clear_logging_context()
        request_id_ctx.set("test-req-123")
        correlation_id_ctx.set("test-corr-456")
        session_id_ctx.set("test-session-789")
        user_ctx.set("test-user")
        role_ctx.set("test-role")

        # Create record
        record = logging.LogRecord(
            name="test-logger",
            level=logging.INFO,
            pathname="verify_logging.py",
            lineno=10,
            msg="This is a test message",
            args=(),
            exc_info=None
        )

        formatter = JsonFormatter()
        formatted_str = formatter.format(record)

        # Parse JSON
        data = json.loads(formatted_str)
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test-logger")
        self.assertEqual(data["message"], "This is a test message")
        self.assertEqual(data["request_id"], "test-req-123")
        self.assertEqual(data["correlation_id"], "test-corr-456")
        self.assertEqual(data["session_id"], "test-session-789")
        self.assertEqual(data["user"], "test-user")
        self.assertEqual(data["role"], "test-role")
        print("[OK] JSON Logging format, serialization, and context variables injection verified.")

if __name__ == "__main__":
    unittest.main()
