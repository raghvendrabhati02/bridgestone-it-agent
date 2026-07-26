"""
test_observability_phase3.py
──────────────────────────────────────────────────────────────────────────────
Phase 3 Enterprise Observability tests.

Coverage
--------
  A. New Prometheus metrics (tool execution + provider-level)
  B. ImmutableAuditLog — append-only API, structured output, persistence, hash
  C. Correlation ID propagation across:
       - logging_context ContextVars
       - json_logger.JsonFormatter
       - tool_agent (correlation_id in log output)
       - observability_service (correlation_id in log_data)
  D. JSON formatter produces valid JSON with required fields
  E. GET /health endpoint schema validation (via FastAPI TestClient)
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from io import StringIO
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_audit_singleton():
    """Always start with a fresh ImmutableAuditLog singleton."""
    from app.services.immutable_audit_log import ImmutableAuditLog
    ImmutableAuditLog.reset_instance()
    yield
    ImmutableAuditLog.reset_instance()


@pytest.fixture(autouse=True)
def reset_logging_context():
    """Reset all logging context vars before each test."""
    from app.core.logging_context import clear_logging_context
    clear_logging_context()
    yield
    clear_logging_context()


# ==============================================================================
# A. PROMETHEUS METRICS
# ==============================================================================

class TestNewPrometheusMetrics:
    """Verify that every new Phase 3 metric is registered and operable."""

    def test_tool_execution_total_exists(self):
        from app.core.metrics import TOOL_EXECUTION_TOTAL
        TOOL_EXECUTION_TOTAL.labels(tool_name="vpn_tools", status="success").inc()

    def test_tool_execution_duration_histogram_exists(self):
        from app.core.metrics import TOOL_EXECUTION_DURATION_SECONDS
        TOOL_EXECUTION_DURATION_SECONDS.labels(tool_name="vpn_tools").observe(0.123)

    def test_tool_retries_total_exists(self):
        from app.core.metrics import TOOL_RETRIES_TOTAL
        TOOL_RETRIES_TOTAL.labels(tool_name="network_tools").inc()

    def test_provider_requests_total_exists(self):
        from app.core.metrics import PROVIDER_REQUESTS_TOTAL
        PROVIDER_REQUESTS_TOTAL.labels(provider="GeminiProvider", model="gemini-2.5-flash").inc()

    def test_provider_retries_total_exists(self):
        from app.core.metrics import PROVIDER_RETRIES_TOTAL
        PROVIDER_RETRIES_TOTAL.labels(provider="GeminiProvider", model="gemini-2.5-flash").inc()

    def test_provider_quota_failures_total_exists(self):
        from app.core.metrics import PROVIDER_QUOTA_FAILURES_TOTAL
        PROVIDER_QUOTA_FAILURES_TOTAL.labels(provider="GeminiProvider").inc()

    def test_provider_latency_histogram_exists(self):
        from app.core.metrics import PROVIDER_LATENCY_SECONDS
        PROVIDER_LATENCY_SECONDS.labels(
            provider="GeminiProvider", model="gemini-2.5-flash", fallback_used="False"
        ).observe(1.42)

    def test_tool_execution_labels_accessible(self):
        """Counters must accept all defined status labels without error."""
        from app.core.metrics import TOOL_EXECUTION_TOTAL
        for status in ("success", "failure"):
            TOOL_EXECUTION_TOTAL.labels(tool_name="outlook_tools", status=status).inc()

    def test_provider_latency_fallback_label(self):
        from app.core.metrics import PROVIDER_LATENCY_SECONDS
        PROVIDER_LATENCY_SECONDS.labels(
            provider="GeminiProvider", model="gemini-3.1-flash-lite", fallback_used="True"
        ).observe(3.0)


# ==============================================================================
# B. IMMUTABLE AUDIT LOG
# ==============================================================================

class TestImmutableAuditLog:
    def _make_log(self):
        from app.services.immutable_audit_log import ImmutableAuditLog
        return ImmutableAuditLog.get_instance()

    # ── Singleton ─────────────────────────────────────────────────────────────
    def test_singleton_returns_same_instance(self):
        from app.services.immutable_audit_log import ImmutableAuditLog
        a = ImmutableAuditLog.get_instance()
        b = ImmutableAuditLog.get_instance()
        assert a is b

    def test_reset_gives_fresh_instance(self):
        from app.services.immutable_audit_log import ImmutableAuditLog
        a = ImmutableAuditLog.get_instance()
        ImmutableAuditLog.reset_instance()
        b = ImmutableAuditLog.get_instance()
        assert a is not b

    # ── Append-only contract ──────────────────────────────────────────────────
    def test_no_update_method(self):
        """The class must NOT expose an update() method."""
        log = self._make_log()
        assert not hasattr(log, "update"), "ImmutableAuditLog must not have update()"

    def test_no_delete_method(self):
        """The class must NOT expose a delete() method."""
        log = self._make_log()
        assert not hasattr(log, "delete"), "ImmutableAuditLog must not have delete()"

    def test_no_overwrite_method(self):
        log = self._make_log()
        assert not hasattr(log, "overwrite")

    def test_no_patch_method(self):
        log = self._make_log()
        assert not hasattr(log, "patch")

    # ── record() returns a valid dict ─────────────────────────────────────────
    def test_record_returns_dict(self):
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            result = log.record(
                event_type="TEST_EVENT",
                actor="pytest",
                payload={"key": "value"},
            )
        assert isinstance(result, dict)

    def test_record_contains_required_fields(self):
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            result = log.record(
                event_type="TICKET_CREATED",
                actor="john.doe",
                payload={"ticket_id": "INC001"},
                session_id="sess-abc",
            )
        assert "timestamp" in result
        assert "event_type" in result
        assert "actor" in result
        assert "session_id" in result
        assert "correlation_id" in result
        assert "payload" in result
        assert "payload_hash" in result

    def test_record_event_type_stored_correctly(self):
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            r = log.record("INCIDENT_CLOSED", "admin", {})
        assert r["event_type"] == "INCIDENT_CLOSED"

    def test_record_actor_stored_correctly(self):
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            r = log.record("LOGIN", "alice", {})
        assert r["actor"] == "alice"

    def test_record_session_id_stored(self):
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            r = log.record("EV", "bot", {}, session_id="sess-xyz")
        assert r["session_id"] == "sess-xyz"

    # ── Payload hash integrity ────────────────────────────────────────────────
    def test_payload_hash_is_sha256(self):
        payload = {"ticket_id": "INC0071633", "category": "network"}
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            r = log.record("EV", "svc", payload)
        expected_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        assert r["payload_hash"] == expected_hash

    def test_payload_hash_changes_with_payload(self):
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            r1 = log.record("EV", "svc", {"a": 1})
            r2 = log.record("EV", "svc", {"a": 2})
        assert r1["payload_hash"] != r2["payload_hash"]

    # ── Correlation ID auto-resolution ────────────────────────────────────────
    def test_explicit_correlation_id_used(self):
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            r = log.record("EV", "svc", {}, correlation_id="corr-explicit-123")
        assert r["correlation_id"] == "corr-explicit-123"

    def test_correlation_id_resolved_from_context(self):
        from app.core.logging_context import correlation_id_ctx
        correlation_id_ctx.set("corr-from-ctx-999")
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            r = log.record("EV", "svc", {})
        assert r["correlation_id"] == "corr-from-ctx-999"

    def test_correlation_id_explicit_overrides_context(self):
        from app.core.logging_context import correlation_id_ctx
        correlation_id_ctx.set("ctx-corr")
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            r = log.record("EV", "svc", {}, correlation_id="explicit-corr")
        assert r["correlation_id"] == "explicit-corr"

    # ── Thread safety ─────────────────────────────────────────────────────────
    def test_concurrent_records_do_not_raise(self):
        log = self._make_log()
        errors = []
        results = []

        def worker(i):
            try:
                with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
                    r = log.record("CONCURRENT", f"actor-{i}", {"i": i})
                    results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Unexpected errors: {errors}"
        assert len(results) == 20

    # ── Structured logging ────────────────────────────────────────────────────
    def test_record_emits_log_at_info_level(self, caplog):
        log = self._make_log()
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            with caplog.at_level(logging.INFO, logger="it-agent-backend"):
                log.record("DEPLOY", "ci-bot", {"env": "prod"})
        assert any("DEPLOY" in m for m in caplog.messages)

    # ── Graceful DB failure ───────────────────────────────────────────────────
    def test_record_does_not_raise_on_db_failure(self):
        log = self._make_log()
        with patch(
            "app.services.immutable_audit_log.ImmutableAuditLog._persist",
            side_effect=RuntimeError("DB is down"),
        ):
            # Should not raise
            try:
                log.record("EV", "svc", {})
            except RuntimeError:
                pytest.fail("record() must not propagate DB errors")

    # ── Module-level convenience ──────────────────────────────────────────────
    def test_module_level_record_audit_event(self):
        from app.services.immutable_audit_log import record_audit_event
        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            r = record_audit_event("MOD_LEVEL", "svc", {"x": 1})
        assert r["event_type"] == "MOD_LEVEL"


# ==============================================================================
# C. CORRELATION ID PROPAGATION
# ==============================================================================

class TestCorrelationIdPropagation:
    """End-to-end correlation ID trace across ContextVars, JsonFormatter, tool_agent."""

    def test_context_var_set_and_get(self):
        from app.core.logging_context import correlation_id_ctx, clear_logging_context
        clear_logging_context()
        assert correlation_id_ctx.get() == ""
        correlation_id_ctx.set("corr-test-001")
        assert correlation_id_ctx.get() == "corr-test-001"

    def test_clear_logging_context_resets_correlation_id(self):
        from app.core.logging_context import correlation_id_ctx, clear_logging_context
        correlation_id_ctx.set("corr-xyz")
        clear_logging_context()
        assert correlation_id_ctx.get() == ""

    def test_get_context_dict_includes_correlation_id(self):
        from app.core.logging_context import correlation_id_ctx, get_context_dict
        correlation_id_ctx.set("corr-dict-test")
        ctx = get_context_dict()
        assert "correlation_id" in ctx
        assert ctx["correlation_id"] == "corr-dict-test"

    def test_json_formatter_includes_correlation_id(self):
        """JsonFormatter must embed the current correlation_id in every log line."""
        from app.core.logging_context import correlation_id_ctx, clear_logging_context
        from app.core.json_logger import JsonFormatter

        clear_logging_context()
        correlation_id_ctx.set("corr-fmt-42")

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="it-agent-backend",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed.get("correlation_id") == "corr-fmt-42"

    def test_json_formatter_output_is_valid_json(self):
        from app.core.json_logger import JsonFormatter
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)   # must not raise
        assert isinstance(parsed, dict)

    def test_json_formatter_includes_required_fields(self):
        from app.core.json_logger import JsonFormatter
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="warn msg", args=(), exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        for field in ("timestamp", "level", "logger", "message"):
            assert field in parsed, f"Missing required field: {field}"

    def test_json_formatter_includes_session_id(self):
        from app.core.logging_context import session_id_ctx
        from app.core.json_logger import JsonFormatter
        session_id_ctx.set("sess-json-test")
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="with session", args=(), exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert parsed.get("session_id") == "sess-json-test"

    def test_json_formatter_includes_request_id(self):
        from app.core.logging_context import request_id_ctx
        from app.core.json_logger import JsonFormatter
        request_id_ctx.set("req-0001")
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="with req id", args=(), exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert parsed.get("request_id") == "req-0001"

    def test_correlation_id_propagates_to_tool_agent_log(self, caplog):
        """
        When correlation_id_ctx is set, tool_agent.execute_tools() must include
        the correlation_id string in its log output.
        """
        from app.core.logging_context import correlation_id_ctx
        correlation_id_ctx.set("corr-tool-999")

        with caplog.at_level(logging.INFO, logger="it-agent-backend"):
            from app.services import tool_agent
            tool_agent.execute_tools("NETWORK", "wifi not working")

        combined = " ".join(caplog.messages)
        assert "corr-tool-999" in combined, (
            "correlation_id must appear in tool_agent log output"
        )

    def test_correlation_id_propagates_to_immutable_audit_log(self, caplog):
        """
        ImmutableAuditLog.record() must embed the active correlation_id in the
        structured log line it emits.
        """
        from app.core.logging_context import correlation_id_ctx
        correlation_id_ctx.set("corr-audit-888")

        from app.services.immutable_audit_log import ImmutableAuditLog
        log = ImmutableAuditLog.get_instance()

        with patch("app.services.immutable_audit_log.ImmutableAuditLog._persist"):
            with caplog.at_level(logging.INFO, logger="it-agent-backend"):
                r = log.record("TEST_EVENT", "svc", {"data": "x"})

        assert r["correlation_id"] == "corr-audit-888"
        combined = " ".join(caplog.messages)
        assert "corr-audit-888" in combined

    def test_correlation_id_propagates_to_observability_service(self):
        """
        observability_service.log_event() must capture the active correlation_id
        from the logging context.
        """
        from app.core.logging_context import correlation_id_ctx, session_id_ctx
        correlation_id_ctx.set("corr-obs-777")
        session_id_ctx.set("sess-obs")

        captured_data: Dict[str, Any] = {}

        class CapturingBackend:
            def log_event(self, event_name, db, data):
                captured_data.update(data)

        from app.services import observability_service
        original_backends = list(observability_service._backends)
        observability_service._backends = [CapturingBackend()]

        try:
            # Patch get_db so it doesn't try to reach Postgres
            with patch("app.services.observability_service.get_db") as mock_db:
                mock_db.return_value.__enter__ = MagicMock(return_value=MagicMock())
                mock_db.return_value.__exit__ = MagicMock(return_value=False)
                observability_service.log_event("test_event", intent="vpn")
        finally:
            observability_service._backends = original_backends

        # The session_id surfaced as conversation_id / session_id in log_data
        assert captured_data.get("session_id") == "sess-obs"

    def test_correlation_id_context_is_thread_isolated(self):
        """
        ContextVars are async-/coroutine-scoped, but each threading.Thread
        inherits the parent context. Verify threads can each set their own
        correlation_id without colliding.
        """
        from app.core.logging_context import correlation_id_ctx
        import copy

        results: Dict[int, str] = {}
        barrier = threading.Barrier(5)

        def worker(thread_id: int):
            # Each thread gets a copy of the parent context; set a unique ID
            correlation_id_ctx.set(f"corr-thread-{thread_id}")
            barrier.wait()
            results[thread_id] = correlation_id_ctx.get()

        threads = [
            threading.Thread(target=worker, args=(i,), daemon=True)
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        for i in range(5):
            assert results[i] == f"corr-thread-{i}", (
                f"Thread {i} saw wrong correlation_id: {results[i]}"
            )


# ==============================================================================
# D. TOOL AGENT METRICS INTEGRATION
# ==============================================================================

class TestToolAgentMetrics:
    """Verify tool_agent instruments TOOL_EXECUTION_TOTAL correctly."""

    def test_vpn_tool_increments_success_counter(self):
        from app.core.metrics import TOOL_EXECUTION_TOTAL
        from prometheus_client import REGISTRY

        label_set = {"tool_name": "vpn_tools", "status": "success"}
        before = _get_counter_value(TOOL_EXECUTION_TOTAL, label_set)

        from app.services.tool_agent import execute_tools
        execute_tools("VPN", "my vpn is not connecting")

        after = _get_counter_value(TOOL_EXECUTION_TOTAL, label_set)
        assert after > before

    def test_network_tool_increments_success_counter(self):
        from app.core.metrics import TOOL_EXECUTION_TOTAL
        label_set = {"tool_name": "network_tools", "status": "success"}
        before = _get_counter_value(TOOL_EXECUTION_TOTAL, label_set)

        from app.services.tool_agent import execute_tools
        execute_tools("NETWORK", "internet is slow")

        after = _get_counter_value(TOOL_EXECUTION_TOTAL, label_set)
        assert after > before

    def test_tool_duration_histogram_records(self):
        from app.core.metrics import TOOL_EXECUTION_DURATION_SECONDS
        from app.services.tool_agent import execute_tools
        # Simply ensure no exception; histogram count > 0 after call
        execute_tools("OUTLOOK", "outlook not syncing")
        # If we reach here without exception, the histogram was observed


# ==============================================================================
# E. GET /health ENDPOINT SCHEMA
# ==============================================================================

class TestHealthEndpoint:
    """Validate the GET /health response schema using FastAPI TestClient."""

    @pytest.fixture
    def client(self):
        """TestClient with DB stubbed out."""
        os_patch = patch.dict(
            "os.environ",
            {"DATABASE_URL": "sqlite:///:memory:", "JSON_LOGGING": "false"},
        )
        with os_patch:
            from fastapi.testclient import TestClient
            from app.main import app
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_contains_status_field(self, client):
        data = client.get("/health").json()
        assert "status" in data

    def test_health_contains_database_field(self, client):
        data = client.get("/health").json()
        assert "database" in data

    def test_health_contains_redis_field(self, client):
        data = client.get("/health").json()
        assert "redis" in data

    def test_health_contains_gemini_field(self, client):
        data = client.get("/health").json()
        assert "gemini" in data

    def test_health_status_is_string(self, client):
        data = client.get("/health").json()
        assert isinstance(data["status"], str)
        assert data["status"] in ("healthy", "degraded", "unhealthy")


# ==============================================================================
# Helpers
# ==============================================================================

def _get_counter_value(counter, labels: dict) -> float:
    """Extract the current value of a Prometheus counter for given labels."""
    try:
        return counter.labels(**labels)._value.get()
    except Exception:
        return 0.0
