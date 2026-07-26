import abc
import os
import re
import json
import logging
import time
import threading
from typing import List, Optional, Dict, Any

try:
    from google import genai as google_genai
    from google.genai import types as genai_types
except ImportError:
    google_genai = None
    genai_types = None

try:
    import anthropic
except ImportError:
    anthropic = None

logger = logging.getLogger("it-agent-backend")

class BaseAIProvider(abc.ABC):
    @abc.abstractmethod
    def is_ready(self) -> bool:
        """Return True if the provider is fully configured and ready to execute calls."""
        pass

    @abc.abstractmethod
    def verify(self) -> bool:
        """Perform API validation/connectivity check once per process."""
        pass

    @abc.abstractmethod
    def chat(self, user_message: str, history: Optional[List[dict]] = None) -> str:
        """Send a user message to the conversational assistant, returning the response text."""
        pass

    @abc.abstractmethod
    def generate_response(self, user_message: str, knowledge_context: Optional[str] = None) -> Any:
        """Generate a single turn response, optionally grounding it with knowledge base context."""
        pass


def _log_gemini_request(func_name: str, user_message: str, model: str):
    try:
        from app.core.logging_context import request_id_ctx, session_id_ctx
        import traceback
        import datetime
        req_id = request_id_ctx.get() if hasattr(request_id_ctx, "get") else "N/A"
        sess_id = session_id_ctx.get() if hasattr(session_id_ctx, "get") else "N/A"
        timestamp = datetime.datetime.now().isoformat()
        
        caller = "Unknown"
        stack = traceback.extract_stack()
        if len(stack) >= 3:
            caller_frame = stack[-3]
            caller = f"{caller_frame.filename}:{caller_frame.lineno} in {caller_frame.name}"
            
        logger.debug("================================================")
        logger.debug("GEMINI REQUEST")
        logger.debug("Function: %s", func_name)
        logger.debug("Caller: %s", caller)
        logger.debug("Request ID: %s", req_id)
        logger.debug("Session ID: %s", sess_id)
        logger.debug("Conversation ID: %s", sess_id)
        logger.debug("Current User Message: %s", user_message)
        logger.debug("Model: %s", model)
        logger.debug("Timestamp: %s", timestamp)
        logger.debug("================================================")
        logger.debug("STACK TRACE:")
        try:
            formatted_stack = "".join(traceback.format_stack())
            logger.debug(formatted_stack)
        except Exception:
            pass
        logger.debug("================================================")
    except Exception:
        logger.exception("Gemini request logging failed")


class GeminiProvider(BaseAIProvider):
    DEFAULT_MODEL = "gemini-2.5-flash"
    DEFAULT_TIMEOUT = 30.0
    SYSTEM_INSTRUCTION = (
        "You are Bridgestone IT Assistant — a professional, concise AI IT support agent "
        "helping Bridgestone employees resolve technology problems. "
        "Always respond in plain English. Never include internal chain-of-thought. "
        "If you cannot resolve an issue, say so clearly."
    )

    def __init__(self, model_name: str | None = None, timeout: float | None = None) -> None:
        if google_genai is None or genai_types is None:
            logger.error("GeminiProvider ERROR: google-genai package is not installed.")
            raise ImportError(
                "GeminiProvider requires the 'google-genai' package. "
                "Please install it using 'pip install google-genai'."
            )

        self._api_key = os.getenv("GEMINI_API_KEY", "")
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._ready = False
        self._verified = False
        self._verify_lock = threading.Lock()
        self._verify_status = "NOT_STARTED"
        self._cached_verify_error = None
        self._api_calls = 0
        self._verify_calls = 0
        
        # Circuit breaker properties
        self._circuit_state = "CLOSED"

        self._circuit_failures = 0
        self._circuit_last_state_change = time.time()
        self._circuit_failure_threshold = 5
        self._circuit_recovery_timeout = 30.0

        if not self._api_key:
            logger.error("GeminiProvider ERROR: GEMINI_API_KEY is not defined in environment variables.")
            raise ValueError(
                "GeminiProvider: GEMINI_API_KEY is not defined in environment variables. "
                "Configure it in backend/.env."
            )

        env_model = os.getenv("GEMINI_MODEL")
        if model_name:
            self._model_name = model_name
        elif env_model:
            self._model_name = env_model
        else:
            logger.warning("GeminiProvider: GEMINI_MODEL is not defined in environment variables. Falling back to default model '%s'.", self.DEFAULT_MODEL)
            self._model_name = self.DEFAULT_MODEL

        logger.info("GeminiProvider: Using model '%s'", self._model_name)

        try:
            timeout_ms = int(self._timeout * 1000)
            self._client = google_genai.Client(
                api_key=self._api_key,
                http_options=genai_types.HttpOptions(timeout=timeout_ms)
            )
            self._ready = True
            logger.info("GeminiProvider: Active provider: GeminiProvider")
            logger.info("GeminiProvider: Model name: %s", self._model_name)
            logger.info("GeminiProvider: Timeout: %.1fs", self._timeout)
            logger.info("GeminiProvider: Provider initialization success")
        except Exception as exc:
            raise RuntimeError(f"GeminiProvider: Generative AI SDK configuration failed: {exc}")

    def is_ready(self) -> bool:
        return self._ready

    def verify(self) -> bool:
        try:
            from app.core.metrics import LLM_VERIFY_TOTAL
            LLM_VERIFY_TOTAL.inc()
        except Exception:
            pass

        self._verify_calls += 1

        if self._verify_status in ("LOCAL_VALIDATED", "READY"):
            return True
        if self._verify_status == "FAILED":
            if isinstance(self._cached_verify_error, ValueError):
                raise self._cached_verify_error
            return False

        with self._verify_lock:
            if self._verify_status in ("LOCAL_VALIDATED", "READY"):
                return True
            if self._verify_status == "FAILED":
                if isinstance(self._cached_verify_error, ValueError):
                    raise self._cached_verify_error
                return False

            self._verify_status = "VERIFYING"
            logger.info("GeminiProvider: Running model verification check...")
            verify_start = time.time()
            try:
                # Local validation checks only (no API network calls)
                if not self._api_key:
                    raise ValueError("GeminiProvider: GEMINI_API_KEY is not defined in environment variables.")
                if not self._model_name:
                    raise ValueError("GeminiProvider: GEMINI_MODEL is not defined in environment variables.")
                if not self._ready or self._client is None:
                    raise ValueError("GeminiProvider: Generative AI SDK client not initialized.")
                
                self._verified = True
                self._verify_status = "LOCAL_VALIDATED"
                
                verify_duration = time.time() - verify_start
                try:
                    from app.core.metrics import LLM_VERIFY_SUCCESS_TOTAL, LLM_VERIFY_DURATION_SECONDS
                    LLM_VERIFY_SUCCESS_TOTAL.inc()
                    LLM_VERIFY_DURATION_SECONDS.observe(verify_duration)
                except Exception:
                    pass
                
                logger.info("GeminiProvider: Verification check completed successfully (Local Validation).")
                return True
            except ValueError as vex:
                self._verify_status = "FAILED"
                self._cached_verify_error = vex
                try:
                    from app.core.metrics import LLM_VERIFY_FAILURE_TOTAL
                    LLM_VERIFY_FAILURE_TOTAL.inc()
                except Exception:
                    pass
                raise
            except Exception as vex:
                self._verify_status = "FAILED"
                self._cached_verify_error = vex
                try:
                    from app.core.metrics import LLM_VERIFY_FAILURE_TOTAL
                    LLM_VERIFY_FAILURE_TOTAL.inc()
                except Exception:
                    pass
                raise ValueError(f"GeminiProvider: Model verification check failed: {vex}")

    def _classify_and_sanitize(self, exc: Exception) -> tuple[str, str]:
        exc_str = str(exc).lower()
        
        # 1. AUTH_ERROR
        if "api key" in exc_str or "auth" in exc_str or "unauthorized" in exc_str or "invalid key" in exc_str or "credentials" in exc_str or "401" in exc_str or "forbidden" in exc_str:
            return (
                "AUTH_ERROR",
                "Authentication failed with the AI service. Please verify the API key configuration."
            )
        
        # 2. RATE_LIMIT
        if "429" in exc_str or "rate limit" in exc_str or "resource exhausted" in exc_str or "quota" in exc_str:
            return (
                "RATE_LIMIT",
                "The AI service rate limit has been exceeded. Please try again in a few moments."
            )
            
        # 3. SERVICE_UNAVAILABLE
        if "503" in exc_str or "unavailable" in exc_str or "busy" in exc_str or "overloaded" in exc_str:
            return (
                "SERVICE_UNAVAILABLE",
                "The AI service is temporarily busy or unavailable. Please try again in a few moments."
            )
            
        # 4. TIMEOUT
        if "timeout" in exc_str or "deadline exceeded" in exc_str or "timed out" in exc_str:
            return (
                "TIMEOUT",
                "The connection to the AI service timed out. Please try again."
            )
            
        # 5. NETWORK_ERROR
        if "network" in exc_str or "connection" in exc_str or "socket" in exc_str or "dns" in exc_str or "unreachable" in exc_str or "reset" in exc_str or "http" in exc_str:
            return (
                "NETWORK_ERROR",
                "A temporary network error occurred while contacting the AI service. Please verify connectivity."
            )
            
        # Default UNKNOWN_ERROR
        return (
            "UNKNOWN_ERROR",
            "An unexpected error occurred while communicating with the AI service."
        )

    def _increment_failure_metric(self, error_class: str) -> None:
        try:
            from app.core.metrics import LLM_FAILURES_TOTAL
            metric_label = error_class
            if metric_label not in ("RATE_LIMIT", "SERVICE_UNAVAILABLE", "TIMEOUT", "NETWORK_ERROR", "UNKNOWN_ERROR"):
                metric_label = "UNKNOWN_ERROR"
            LLM_FAILURES_TOTAL.labels(error_type=metric_label).inc()
        except Exception as mex:
            logger.warning("Failed to increment LLM failure metric: %s", mex)

    def _get_retry_delay(self, exc: Exception) -> float | None:
        try:
            if hasattr(exc, "details") and isinstance(exc.details, dict):
                error_details = exc.details.get("error", {}).get("details", [])
                for detail in error_details:
                    if isinstance(detail, dict) and detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                        delay_str = detail.get("retryDelay", "")
                        if delay_str.endswith("s"):
                            return float(delay_str[:-1])
                        return float(delay_str)
        except Exception as parse_exc:
            logger.warning("Failed to parse RetryInfo from exception: %s", parse_exc)
        
        try:
            import re
            m = re.search(r"retryDelay\D*(\d+)", str(exc))
            if m:
                return float(m.group(1))
        except Exception:
            pass
            
        return None

    def _check_circuit(self) -> None:
        now = time.time()
        if self._circuit_state == "OPEN":
            if now - self._circuit_last_state_change > self._circuit_recovery_timeout:
                logger.info("Circuit Breaker: Entering HALF_OPEN state to test request.")
                self._circuit_state = "HALF_OPEN"
                self._circuit_last_state_change = now
            else:
                raise RuntimeError(
                    "Circuit Breaker: Gemini Provider is currently unavailable due to repeated failures (Circuit is OPEN)."
                )

    def _record_success(self) -> None:
        if self._circuit_state == "HALF_OPEN":
            logger.info("Circuit Breaker: Request succeeded. Closing circuit.")
            self._circuit_state = "CLOSED"
        self._circuit_failures = 0
        self._circuit_last_state_change = time.time()
        
        # Transition verification state machine to READY upon first successful request
        if self._verify_status in ("LOCAL_VALIDATED", "NOT_STARTED"):
            self._verify_status = "READY"

    def _record_failure(self, error_class: str) -> None:
        if error_class not in ("RATE_LIMIT", "SERVICE_UNAVAILABLE", "TIMEOUT", "NETWORK_ERROR"):
            return
        self._circuit_failures += 1
        now = time.time()
        if self._circuit_state in ("CLOSED", "HALF_OPEN"):
            if self._circuit_failures >= self._circuit_failure_threshold or self._circuit_state == "HALF_OPEN":
                logger.warning(
                    "Circuit Breaker: Transitioning to OPEN state due to %d consecutive failures.",
                    self._circuit_failures
                )
                self._circuit_state = "OPEN"
                self._circuit_last_state_change = now

    def _execute_with_retry(self, func, max_retries=3, *args, **kwargs):
        self._check_circuit()
        backoff = [1, 2, 4]
        
        for attempt in range(max_retries + 1):  # 0, 1, 2, 3 (maximum 3 retries, i.e., 4 total attempts)
            try:
                # Debug logging before request
                logger.debug(
                    "AI Provider Call Attempt: Provider=GeminiProvider, Model=%s, Attempt=%d/%d",
                    self._model_name, attempt + 1, max_retries + 1
                )
                res = func(*args, **kwargs)
                self._record_success()
                return res
            except Exception as exc:
                error_class, _ = self._classify_and_sanitize(exc)
                exc_type = type(exc).__name__
                exc_str = str(exc).lower()
                is_404 = "404" in exc_str or "not found" in exc_str or "not_found" in exc_str
                
                # Check for permanent configuration errors
                if error_class == "AUTH_ERROR" or is_404:
                    self._verify_status = "FAILED"
                    self._cached_verify_error = ValueError(f"GeminiProvider: Permanent configuration error: {exc}")
                
                # Debug logging on failure
                logger.debug(
                    "AI Provider Call Failed: Provider=GeminiProvider, Model=%s, ExceptionType=%s, ErrorCategory=%s, Attempt=%d/%d",
                    self._model_name, exc_type, error_class, attempt + 1, max_retries + 1
                )
                
                is_retryable = error_class in ("RATE_LIMIT", "SERVICE_UNAVAILABLE", "TIMEOUT", "NETWORK_ERROR")
                
                if is_retryable and attempt < max_retries:
                    retry_delay = self._get_retry_delay(exc)
                    wait_time = retry_delay if retry_delay is not None else backoff[attempt]
                    if wait_time > 2.0:
                        logger.warning("GeminiProvider: Retry delay %.2f is too large (> 2.0s). Skipping retry to fail fast/fallback.", wait_time)
                        self._record_failure(error_class)
                        raise exc
                    logger.warning("GeminiProvider: Temporary error detected (%s).", error_class)
                    logger.warning("Retry %d/3 after %.2f seconds. (Exception: %s)", attempt + 1, wait_time, exc_type)
                    time.sleep(wait_time)
                else:
                    self._record_failure(error_class)
                    raise exc

    def _execute_with_fallback(self, api_call_func):
        from app.core.logging_context import request_id_ctx, correlation_id_ctx, session_id_ctx
        
        start_time = time.time()
        start_api_calls = self._api_calls
        start_verify_calls = self._verify_calls
        model_used = self._model_name
        fallback_used = False
        primary_attempts = 0
        fallback_attempts = 0
        
        def wrap_call(model_name):
            nonlocal primary_attempts, model_used
            primary_attempts += 1
            model_used = model_name
            return api_call_func(model_name)

        try:
            # Try configured model with default retries according to the centralized retry policy
            res = self._execute_with_retry(lambda: wrap_call(self._model_name), max_retries=3)
            latency = time.time() - start_time

            logical_api_calls = self._api_calls - start_api_calls
            logical_verify_calls = self._verify_calls - start_verify_calls
            total_retries = max(0, primary_attempts - 1)

            # Observe per-provider + per-model metrics
            try:
                from app.core.metrics import (
                    LLM_REQUEST_DURATION_SECONDS,
                    PROVIDER_REQUESTS_TOTAL,
                    PROVIDER_RETRIES_TOTAL,
                    PROVIDER_LATENCY_SECONDS,
                )
                LLM_REQUEST_DURATION_SECONDS.labels(
                    model=model_used, fallback_used=str(fallback_used)
                ).observe(latency)
                PROVIDER_REQUESTS_TOTAL.labels(
                    provider="GeminiProvider", model=model_used
                ).inc()
                if total_retries > 0:
                    PROVIDER_RETRIES_TOTAL.labels(
                        provider="GeminiProvider", model=model_used
                    ).inc(total_retries)
                PROVIDER_LATENCY_SECONDS.labels(
                    provider="GeminiProvider",
                    model=model_used,
                    fallback_used=str(fallback_used),
                ).observe(latency)
            except Exception:
                pass
                
            # Log structured log on success
            logger.info(
                "Structured LLM Call - Request ID: '%s', Session ID: '%s', Conversation ID: '%s', "
                "Provider: 'GeminiProvider', Model: '%s', Latency: %.4fs, Retry Count: %d, Fallback Used: %s, Actual Gemini API Calls: %d",
                request_id_ctx.get(), session_id_ctx.get(), correlation_id_ctx.get(),
                model_used, latency, total_retries, str(fallback_used), logical_api_calls
            )
            
            logger.info(
                "Logical Request : 1\n"
                "Actual Gemini Calls : %d\n"
                "Verify Calls : %d\n"
                "Retries : %d\n"
                "Fallback Used : %s",
                logical_api_calls,
                logical_verify_calls,
                total_retries,
                str(fallback_used)
            )
            return res
        except Exception as exc:
            error_class, _ = self._classify_and_sanitize(exc)
            exc_str = str(exc).lower()
            is_404 = "404" in exc_str or "not found" in exc_str or "not_found" in exc_str
            is_503 = "503" in exc_str or "unavailable" in exc_str or "overloaded" in exc_str or error_class == "SERVICE_UNAVAILABLE"
            is_429 = "429" in exc_str or "quota" in exc_str or "limit" in exc_str or error_class == "RATE_LIMIT"

            # Record quota/rate-limit failure per provider
            if is_429:
                try:
                    from app.core.metrics import PROVIDER_QUOTA_FAILURES_TOTAL
                    PROVIDER_QUOTA_FAILURES_TOTAL.labels(provider="GeminiProvider").inc()
                except Exception:
                    pass

            if is_404 or is_503 or is_429:
                fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite").strip()
                fallback_used = True
                logger.warning(
                    "GeminiProvider: Primary model '%s' failed (error_class=%s). "
                    "Falling back to '%s'...",
                    self._model_name, error_class, fallback_model
                )

                # Increment fallback metric
                try:
                    from app.core.metrics import LLM_MODEL_FALLBACK_TOTAL
                    LLM_MODEL_FALLBACK_TOTAL.labels(
                        target_model=self._model_name,
                        fallback_model=fallback_model,
                        reason=f"error_class={error_class}"
                    ).inc()
                except Exception as mex:
                    logger.warning("Failed to increment LLM model fallback metric: %s", mex)

                def wrap_fallback_call(model_name):
                    nonlocal fallback_attempts, model_used
                    fallback_attempts += 1
                    model_used = model_name
                    return api_call_func(model_name)

                fallback_start = time.time()
                try:
                    # Execute on fallback model with default retries according to the centralized retry policy
                    res = self._execute_with_retry(lambda: wrap_fallback_call(fallback_model), max_retries=3)
                    
                    total_latency = time.time() - start_time
                    fallback_latency = time.time() - fallback_start
                    logical_api_calls = self._api_calls - start_api_calls
                    logical_verify_calls = self._verify_calls - start_verify_calls
                    total_retries = max(0, primary_attempts - 1) + max(0, fallback_attempts - 1)
                    
                    # Observe latency metrics
                    try:
                        from app.core.metrics import LLM_REQUEST_DURATION_SECONDS, LLM_FALLBACK_DURATION_SECONDS
                        LLM_REQUEST_DURATION_SECONDS.labels(
                            model=model_used,
                            fallback_used=str(fallback_used)
                        ).observe(total_latency)
                        LLM_FALLBACK_DURATION_SECONDS.labels(
                            target_model=self._model_name,
                            fallback_model=fallback_model
                        ).observe(fallback_latency)
                    except Exception:
                        pass
                    
                    logger.info(
                        "Structured LLM Call - Request ID: '%s', Session ID: '%s', Conversation ID: '%s', "
                        "Provider: 'GeminiProvider', Model: '%s', Latency: %.4fs, Retry Count: %d, Fallback Used: %s, Actual Gemini API Calls: %d",
                        request_id_ctx.get(), session_id_ctx.get(), correlation_id_ctx.get(),
                        model_used, total_latency, total_retries, str(fallback_used), logical_api_calls
                    )
                    logger.info(
                        "Logical Request : 1\n"
                        "Actual Gemini Calls : %d\n"
                        "Verify Calls : %d\n"
                        "Retries : %d\n"
                        "Fallback Used : %s",
                        logical_api_calls,
                        logical_verify_calls,
                        total_retries,
                        str(fallback_used)
                    )
                    return res
                except Exception as fallback_exc:
                    total_latency = time.time() - start_time
                    logical_api_calls = self._api_calls - start_api_calls
                    logical_verify_calls = self._verify_calls - start_verify_calls
                    total_retries = max(0, primary_attempts - 1) + max(0, fallback_attempts - 1)
                    logger.error(
                        "Structured LLM Call FAILED - Request ID: '%s', Session ID: '%s', Conversation ID: '%s', "
                        "Provider: 'GeminiProvider', Model: '%s', Latency: %.4fs, Retry Count: %d, Fallback Used: %s, Actual Gemini API Calls: %d, Error: %s",
                        request_id_ctx.get(), session_id_ctx.get(), correlation_id_ctx.get(),
                        model_used, total_latency, total_retries, str(fallback_used), logical_api_calls, fallback_exc
                    )
                    logger.info(
                        "Logical Request : 1\n"
                        "Actual Gemini Calls : %d\n"
                        "Verify Calls : %d\n"
                        "Retries : %d\n"
                        "Fallback Used : %s",
                        logical_api_calls,
                        logical_verify_calls,
                        total_retries,
                        str(fallback_used)
                    )
                    raise fallback_exc
            else:
                latency = time.time() - start_time
                logical_api_calls = self._api_calls - start_api_calls
                logical_verify_calls = self._verify_calls - start_verify_calls
                total_retries = max(0, primary_attempts - 1)
                logger.error(
                    "Structured LLM Call FAILED - Request ID: '%s', Session ID: '%s', Conversation ID: '%s', "
                    "Provider: 'GeminiProvider', Model: '%s', Latency: %.4fs, Retry Count: %d, Fallback Used: %s, Actual Gemini API Calls: %d, Error: %s",
                    request_id_ctx.get(), session_id_ctx.get(), correlation_id_ctx.get(),
                    model_used, latency, total_retries, str(fallback_used), logical_api_calls, exc
                )
                logger.info(
                    "Logical Request : 1\n"
                    "Actual Gemini Calls : %d\n"
                    "Verify Calls : %d\n"
                    "Retries : %d\n"
                    "Fallback Used : %s",
                    logical_api_calls,
                    logical_verify_calls,
                    total_retries,
                    str(fallback_used)
                )
                raise exc


    def chat(self, user_message: str, history: Optional[List[dict]] = None) -> str:
        history = history or []
        try:
            sdk_history = []
            for turn in history:
                role = turn.get("role")
                text = turn.get("text")
                if role in ("user", "model") and text:
                    sdk_history.append(
                        genai_types.Content(
                            role=role,
                            parts=[genai_types.Part.from_text(text=text)]
                        )
                    )

            def _chat_call(model_to_use):
                from app.core.logging_context import request_id_ctx, session_id_ctx
                import traceback
                req_id = request_id_ctx.get() or "N/A"
                sess_id = session_id_ctx.get() or "N/A"
                
                self._api_calls += 1
                chat_session = self._client.chats.create(
                    model=model_to_use,
                    history=sdk_history,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_INSTRUCTION
                    )
                )
                _log_gemini_request("chat", user_message, model_to_use)
                logger.info(">>> Before send_message() | Request ID: %s | Session ID: %s | Model: %s", req_id, sess_id, model_to_use)
                t_api = time.time()
                try:
                    response = chat_session.send_message(user_message)
                    elapsed_api = (time.time() - t_api) * 1000
                    logger.info("<<< After send_message() - %.2f ms | Request ID: %s | Session ID: %s", elapsed_api, req_id, sess_id)
                except Exception as exc:
                    elapsed_api = (time.time() - t_api) * 1000
                    logger.error(
                        "!!! Failure in send_message() - %.2f ms | Request ID: %s | Session ID: %s | Error: %s | Traceback: %s",
                        elapsed_api, req_id, sess_id, exc, traceback.format_exc()
                    )
                    raise
                if not response or not response.text:
                    raise ValueError("Gemini returned an empty response.")
                return response.text.strip()

            return self._execute_with_fallback(_chat_call)
        except Exception as exc:
            logger.exception("GeminiProvider.chat exception: %s", exc)
            error_class, user_msg = self._classify_and_sanitize(exc)
            self._increment_failure_metric(error_class)
            return f"[AI Provider Error] {user_msg}"

    def generate_response(self, user_message: str, knowledge_context: Optional[str] = None) -> Any:
        from app.core.metrics import (
            LLM_REQUESTS_TOTAL,
            LLM_SUCCESS_TOTAL,
            LLM_FAILURES_TOTAL,
            LLM_LATENCY_SECONDS,
            LLM_TOKEN_USAGE_TOTAL,
            LLM_RATE_LIMIT_ERRORS_TOTAL,
            LLM_FALLBACK_EVENTS_TOTAL
        )
        try:
            LLM_REQUESTS_TOTAL.inc()
        except Exception:
            pass

        start_time = time.time()

        if knowledge_context:
            prompt = (
                "You are a Level-1/Level-2 IT Support Engineer at Bridgestone.\n"
                "Use your own technical knowledge and reasoning to troubleshoot the user's issue.\n"
                "The knowledge base below contains company-specific policies, procedures, and internal "
                "configurations — use it as a supporting reference when it is relevant, and give it "
                "precedence over general IT knowledge for any company-specific topics.\n\n"
                "=== COMPANY KNOWLEDGE BASE ===\n"
                f"{knowledge_context}\n\n"
                "=== USER QUESTION ===\n"
                f"{user_message}\n\n"
                "Provide a concise, professional troubleshooting response that combines your IT reasoning "
                "with any relevant internal procedures from the knowledge base above."
            )
        else:
            prompt = user_message

        try:
            def _gen_call(model_to_use):
                from app.core.logging_context import request_id_ctx, session_id_ctx
                import traceback
                req_id = request_id_ctx.get() or "N/A"
                sess_id = session_id_ctx.get() or "N/A"
                
                self._api_calls += 1
                _log_gemini_request("generate_response", user_message, model_to_use)
                logger.info(">>> Before generate_content() | Request ID: %s | Session ID: %s | Model: %s", req_id, sess_id, model_to_use)
                t_api = time.time()
                try:
                    response = self._client.models.generate_content(
                        model=model_to_use,
                        contents=prompt,
                        config=genai_types.GenerateContentConfig(
                            http_options=genai_types.HttpOptions(timeout=15000)
                        )
                    )
                    elapsed_api = (time.time() - t_api) * 1000
                    logger.info("<<< After generate_content() - %.2f ms | Request ID: %s | Session ID: %s", elapsed_api, req_id, sess_id)
                except Exception as exc:
                    elapsed_api = (time.time() - t_api) * 1000
                    logger.error(
                        "!!! Failure in generate_content() - %.2f ms | Request ID: %s | Session ID: %s | Error: %s | Traceback: %s",
                        elapsed_api, req_id, sess_id, exc, traceback.format_exc()
                    )
                    raise
                if not response or not response.text:
                    raise ValueError("Gemini returned empty text response.")
                return response

            response = self._execute_with_fallback(_gen_call)

            duration = time.time() - start_time
            try:
                LLM_LATENCY_SECONDS.observe(duration)
                from app.core.metrics import AI_LATENCIES
                AI_LATENCIES.append(duration)
                if len(AI_LATENCIES) > 100:
                    AI_LATENCIES.pop(0)
            except Exception:
                pass

            parsed_text = response.text.strip()

            try:
                LLM_SUCCESS_TOTAL.inc()
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_token_count", 0)
                    candidate_tokens = getattr(usage, "candidates_token_count", 0)
                    if prompt_tokens:
                        LLM_TOKEN_USAGE_TOTAL.labels(token_type="prompt_tokens").inc(prompt_tokens)
                    if candidate_tokens:
                        LLM_TOKEN_USAGE_TOTAL.labels(token_type="candidate_tokens").inc(candidate_tokens)
            except Exception as mex:
                logger.warning("Failed to record LLM usage metrics: %s", mex)

            return parsed_text


        except Exception as e:
            duration = time.time() - start_time
            logger.exception("GeminiProvider generate_response exception: %s", e)
            error_class, user_msg = self._classify_and_sanitize(e)

            try:
                LLM_LATENCY_SECONDS.observe(duration)
                from app.core.metrics import AI_LATENCIES
                AI_LATENCIES.append(duration)
                if len(AI_LATENCIES) > 100:
                    AI_LATENCIES.pop(0)
                
                self._increment_failure_metric(error_class)
                
                if error_class == "RATE_LIMIT":
                    LLM_RATE_LIMIT_ERRORS_TOTAL.inc()
                
                LLM_FALLBACK_EVENTS_TOTAL.inc()
            except Exception:
                pass

            return {
                "success": False,
                "error_type": error_class,
                "message": user_msg,
                "debug_error": user_msg  # Kept for backward compatibility, marked for future removal
            }

class ClaudeProvider(BaseAIProvider):
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    DEFAULT_TIMEOUT = 30.0
    SYSTEM_INSTRUCTION = (
        "You are Bridgestone IT Assistant — a professional, concise AI IT support agent "
        "helping Bridgestone employees resolve technology problems. "
        "Always respond in plain English. Never include internal chain-of-thought. "
        "If you cannot resolve an issue, say so clearly."
    )

    def __init__(self, model_name: str | None = None, timeout: float | None = None) -> None:
        if anthropic is None:
            logger.error("ClaudeProvider ERROR: anthropic package is not installed.")
            raise ImportError(
                "ClaudeProvider requires the 'anthropic' package. "
                "Please install it using 'pip install anthropic'."
            )

        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._ready = False
        self._verified = False
        self._verify_lock = threading.Lock()
        self._verify_status = "NOT_STARTED"
        self._cached_verify_error = None
        self._api_calls = 0
        self._verify_calls = 0


        if not self._api_key:
            logger.error("ClaudeProvider ERROR: ANTHROPIC_API_KEY is not defined in environment variables.")
            raise ValueError(
                "ClaudeProvider: ANTHROPIC_API_KEY is not defined in environment variables. "
                "Configure it in backend/.env."
            )

        env_model = os.getenv("CLAUDE_MODEL")
        if model_name:
            self._model_name = model_name
        elif env_model:
            self._model_name = env_model
        else:
            logger.warning("ClaudeProvider: CLAUDE_MODEL is not defined in environment variables. Falling back to default model '%s'.", self.DEFAULT_MODEL)
            self._model_name = self.DEFAULT_MODEL

        logger.info("ClaudeProvider: Using model '%s'", self._model_name)

        try:
            self._client = anthropic.Anthropic(
                api_key=self._api_key,
                timeout=self._timeout
            )
            self._ready = True
            logger.info("ClaudeProvider: Active provider: ClaudeProvider")
            logger.info("ClaudeProvider: Model name: %s", self._model_name)
            logger.info("ClaudeProvider: Timeout: %.1fs", self._timeout)
            logger.info("ClaudeProvider: Provider initialization success")
        except Exception as exc:
            raise RuntimeError(f"ClaudeProvider: Generative AI SDK configuration failed: {exc}")

    def is_ready(self) -> bool:
        return self._ready

    def verify(self) -> bool:
        self._verify_calls += 1

        if self._verify_status in ("LOCAL_VALIDATED", "READY"):
            return True
        if self._verify_status == "FAILED":
            if isinstance(self._cached_verify_error, ValueError):
                raise self._cached_verify_error
            return False

        with self._verify_lock:
            if self._verify_status in ("LOCAL_VALIDATED", "READY"):
                return True
            if self._verify_status == "FAILED":
                if isinstance(self._cached_verify_error, ValueError):
                    raise self._cached_verify_error
                return False

            self._verify_status = "VERIFYING"
            logger.info("ClaudeProvider: Running model verification check...")
            try:
                # Local validation checks only (no API network calls)
                if not self._api_key:
                    raise ValueError("ClaudeProvider: ANTHROPIC_API_KEY is not defined in environment variables.")
                if not self._model_name:
                    raise ValueError("ClaudeProvider: CLAUDE_MODEL is not defined in environment variables.")
                if not self._ready or self._client is None:
                    raise ValueError("ClaudeProvider: Anthropic SDK client not initialized.")
                
                self._verified = True
                self._verify_status = "LOCAL_VALIDATED"
                logger.info("ClaudeProvider: Verification check completed successfully (Local Validation).")
                return True
            except ValueError as vex:
                self._verify_status = "FAILED"
                self._cached_verify_error = vex
                raise
            except Exception as vex:
                self._verify_status = "FAILED"
                self._cached_verify_error = vex
                raise ValueError(f"ClaudeProvider: Model verification check failed: {vex}")

    def _classify_and_sanitize(self, exc: Exception) -> tuple[str, str]:
        exc_str = str(exc).lower()
        
        # Check Anthropic SDK exceptions or keywords
        if "AuthenticationError" in type(exc).__name__ or "api key" in exc_str or "auth" in exc_str or "unauthorized" in exc_str or "forbidden" in exc_str or "401" in exc_str:
            return (
                "AUTH_ERROR",
                "Authentication failed with the AI service. Please verify the API key configuration."
            )
        
        if "RateLimitError" in type(exc).__name__ or "429" in exc_str or "rate limit" in exc_str or "resource exhausted" in exc_str or "quota" in exc_str:
            return (
                "RATE_LIMIT",
                "The AI service rate limit has been exceeded. Please try again in a few moments."
            )
            
        if "503" in exc_str or "unavailable" in exc_str or "busy" in exc_str or "overloaded" in exc_str:
            return (
                "SERVICE_UNAVAILABLE",
                "The AI service is temporarily busy or unavailable. Please try again in a few moments."
            )
            
        if "APITimeoutError" in type(exc).__name__ or "timeout" in exc_str or "deadline exceeded" in exc_str or "timed out" in exc_str:
            return (
                "TIMEOUT",
                "The connection to the AI service timed out. Please try again."
            )
            
        if "APIConnectionError" in type(exc).__name__ or "network" in exc_str or "connection" in exc_str or "socket" in exc_str or "dns" in exc_str or "unreachable" in exc_str or "reset" in exc_str or "http" in exc_str:
            return (
                "NETWORK_ERROR",
                "A temporary network error occurred while contacting the AI service. Please verify connectivity."
            )
            
        return (
            "UNKNOWN_ERROR",
            "An unexpected error occurred while communicating with the AI service."
        )

    def _increment_failure_metric(self, error_class: str) -> None:
        try:
            from app.core.metrics import LLM_FAILURES_TOTAL
            metric_label = error_class
            if metric_label not in ("RATE_LIMIT", "SERVICE_UNAVAILABLE", "TIMEOUT", "NETWORK_ERROR", "UNKNOWN_ERROR"):
                metric_label = "UNKNOWN_ERROR"
            LLM_FAILURES_TOTAL.labels(error_type=metric_label).inc()
        except Exception as mex:
            logger.warning("Failed to increment LLM failure metric: %s", mex)

    def _execute_with_retry(self, func, *args, **kwargs):
        max_retries = 3
        backoff = [1, 2, 4]
        
        for attempt in range(max_retries + 1):  # 0, 1, 2, 3 (maximum 3 retries, i.e., 4 total attempts)
            try:
                # Debug logging before request
                logger.debug(
                    "AI Provider Call Attempt: Provider=ClaudeProvider, Model=%s, Attempt=%d/%d",
                    self._model_name, attempt + 1, max_retries + 1
                )
                res = func(*args, **kwargs)
                if self._verify_status in ("LOCAL_VALIDATED", "NOT_STARTED"):
                    self._verify_status = "READY"
                return res
            except Exception as exc:
                error_class, _ = self._classify_and_sanitize(exc)
                exc_type = type(exc).__name__
                exc_str = str(exc).lower()
                is_404 = "404" in exc_str or "not found" in exc_str or "not_found" in exc_str
                
                # Check for permanent configuration errors
                if error_class == "AUTH_ERROR" or is_404:
                    self._verify_status = "FAILED"
                    self._cached_verify_error = ValueError(f"ClaudeProvider: Permanent configuration error: {exc}")
                
                # Debug logging on failure
                logger.debug(
                    "AI Provider Call Failed: Provider=ClaudeProvider, Model=%s, ExceptionType=%s, ErrorCategory=%s, Attempt=%d/%d",
                    self._model_name, exc_type, error_class, attempt + 1, max_retries + 1
                )
                
                is_retryable = error_class in ("RATE_LIMIT", "SERVICE_UNAVAILABLE", "TIMEOUT", "NETWORK_ERROR")
                
                if is_retryable and attempt < max_retries:
                    wait_time = backoff[attempt]
                    logger.warning("ClaudeProvider: Temporary error detected.")
                    logger.warning("Retry %d/3 after %d seconds. (Exception: %s)", attempt + 1, wait_time, exc_type)
                    time.sleep(wait_time)
                else:
                    raise exc

    def chat(self, user_message: str, history: Optional[List[dict]] = None) -> str:
        history = history or []
        try:
            sdk_messages = []
            for turn in history:
                role = turn.get("role")
                text = turn.get("text")
                sdk_role = "assistant" if role == "model" else "user"
                if text:
                    sdk_messages.append({
                        "role": sdk_role,
                        "content": text
                    })

            sdk_messages.append({
                "role": "user",
                "content": user_message
            })

            def _chat_call():
                self._api_calls += 1
                response = self._client.messages.create(
                    model=self._model_name,
                    messages=sdk_messages,
                    system=self.SYSTEM_INSTRUCTION,
                    max_tokens=2048
                )
                if not response or not response.content:
                    raise ValueError("Claude returned an empty response.")
                
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text
                if not text:
                    raise ValueError("Claude returned empty text content.")
                return text.strip()

            return self._execute_with_retry(_chat_call)
        except Exception as exc:
            logger.exception("ClaudeProvider.chat exception: %s", exc)
            error_class, user_msg = self._classify_and_sanitize(exc)
            self._increment_failure_metric(error_class)
            return f"[AI Provider Error] {user_msg}"

    def generate_response(self, user_message: str, knowledge_context: Optional[str] = None) -> Any:
        from app.core.metrics import (
            LLM_REQUESTS_TOTAL,
            LLM_SUCCESS_TOTAL,
            LLM_FAILURES_TOTAL,
            LLM_LATENCY_SECONDS,
            LLM_TOKEN_USAGE_TOTAL,
            LLM_RATE_LIMIT_ERRORS_TOTAL,
            LLM_FALLBACK_EVENTS_TOTAL
        )
        try:
            LLM_REQUESTS_TOTAL.inc()
        except Exception:
            pass

        start_time = time.time()

        if knowledge_context:
            prompt = (
                "You are a Level-1/Level-2 IT Support Engineer at Bridgestone.\n"
                "Use your own technical knowledge and reasoning to troubleshoot the user's issue.\n"
                "The knowledge base below contains company-specific policies, procedures, and internal "
                "configurations — use it as a supporting reference when it is relevant, and give it "
                "precedence over general IT knowledge for any company-specific topics.\n\n"
                "=== COMPANY KNOWLEDGE BASE ===\n"
                f"{knowledge_context}\n\n"
                "=== USER QUESTION ===\n"
                f"{user_message}\n\n"
                "Provide a concise, professional troubleshooting response that combines your IT reasoning "
                "with any relevant internal procedures from the knowledge base above."
            )
        else:
            prompt = user_message

        try:
            def _gen_call():
                self._api_calls += 1
                response = self._client.messages.create(
                    model=self._model_name,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                if not response or not response.content:
                    raise ValueError("Claude returned empty response.")
                
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text
                if not text:
                    raise ValueError("Claude returned empty text content.")
                return response, text.strip()

            response_obj, parsed_text = self._execute_with_retry(_gen_call)

            duration = time.time() - start_time
            try:
                LLM_LATENCY_SECONDS.observe(duration)
                from app.core.metrics import AI_LATENCIES
                AI_LATENCIES.append(duration)
                if len(AI_LATENCIES) > 100:
                    AI_LATENCIES.pop(0)
            except Exception:
                pass

            try:
                LLM_SUCCESS_TOTAL.inc()
                usage = getattr(response_obj, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "input_tokens", 0)
                    candidate_tokens = getattr(usage, "output_tokens", 0)
                    if prompt_tokens:
                        LLM_TOKEN_USAGE_TOTAL.labels(token_type="prompt_tokens").inc(prompt_tokens)
                    if candidate_tokens:
                        LLM_TOKEN_USAGE_TOTAL.labels(token_type="candidate_tokens").inc(candidate_tokens)
            except Exception as mex:
                logger.warning("Failed to record LLM usage metrics: %s", mex)

            return parsed_text

        except Exception as e:
            duration = time.time() - start_time
            logger.exception("ClaudeProvider generate_response exception: %s", e)
            error_class, user_msg = self._classify_and_sanitize(e)

            try:
                LLM_LATENCY_SECONDS.observe(duration)
                from app.core.metrics import AI_LATENCIES
                AI_LATENCIES.append(duration)
                if len(AI_LATENCIES) > 100:
                    AI_LATENCIES.pop(0)
                
                self._increment_failure_metric(error_class)
                
                if error_class == "RATE_LIMIT":
                    LLM_RATE_LIMIT_ERRORS_TOTAL.inc()
                
                LLM_FALLBACK_EVENTS_TOTAL.inc()
            except Exception:
                pass

            return {
                "success": False,
                "error_type": error_class,
                "message": user_msg,
                "debug_error": user_msg
            }


class MockProvider(BaseAIProvider):
    def is_ready(self) -> bool:
        return True

    def verify(self) -> bool:
        return True

    def chat(self, user_message: str, history: Optional[List[dict]] = None) -> str:
        prompt_str = (user_message or "").lower()
        raw_user_msg = prompt_str
        if "user's latest response:" in prompt_str:
            raw_user_msg = prompt_str.split("user's latest response:")[-1].strip()

        is_decision_mode = bool(history and any("required json format" in str(t.get("text","")).lower() for t in history))
        actual_history = (history or [])[2:] if is_decision_mode else (history or [])
        hist_str = "".join([str(t.get("text","")).lower() for t in actual_history])
        combined = raw_user_msg + " " + hist_str

        if is_decision_mode or "assistant_message" in combined:
            if any(w in raw_user_msg for w in ["yes", "approve", "proceed", "go ahead"]):
                if "vpn" in combined:
                    return json.dumps({
                        "assistant_message": "Restoration request approved. Initiating VPN access restoration.",
                        "intent": "VPN_ACCESS_RESTORE",
                        "tool": "VPN_ACCESS_RESTORE",
                        "parameters": {},
                        "confidence": 0.95,
                        "requires_confirmation": False,
                        "action_type": "STEP",
                        "escalation_reason": None
                    })
                elif "software" in combined or "install" in combined:
                    return json.dumps({
                        "assistant_message": "Software installation ticket request approved. Creating ticket.",
                        "intent": "INSTALL_SOFTWARE",
                        "tool": "CREATE_TICKET",
                        "parameters": {},
                        "confidence": 0.95,
                        "requires_confirmation": False,
                        "action_type": "STEP",
                        "escalation_reason": None
                    })
                elif "unblock" in combined or "account" in combined or "lock" in combined or "ad" in combined:
                    return json.dumps({
                        "assistant_message": "AD account unlock request approved. Unlocking account.",
                        "intent": "UNLOCK_AD_USER",
                        "tool": "UNLOCK_AD_USER",
                        "parameters": {},
                        "confidence": 0.95,
                        "requires_confirmation": False,
                        "action_type": "STEP",
                        "escalation_reason": None
                    })

            elif any(w in raw_user_msg for w in ["ticket", "escalate", "human"]):
                return json.dumps({
                    "assistant_message": "I'll be happy to help you create a support ticket for this issue. Shall I proceed?",
                    "intent": "CREATE_TICKET",
                    "tool": "CREATE_TICKET",
                    "parameters": {},
                    "confidence": 0.95,
                    "requires_confirmation": True,
                    "action_type": "QUESTION",
                    "escalation_reason": "USER_REQUESTED"
                })

            else:
                if any(w in raw_user_msg for w in ["flight", "paris", "book", "unrelated", "vacation"]):
                    return json.dumps({
                        "assistant_message": "I am an IT Support Assistant designed to help with technical issues. I am unable to assist with non-IT queries.",
                        "intent": "GENERAL_SUPPORT",
                        "tool": None,
                        "parameters": {},
                        "confidence": 0.95,
                        "requires_confirmation": False,
                        "action_type": "OTHER",
                        "escalation_reason": None
                    })

                # Determine category
                cat = "general"
                if "vpn" in combined:
                    cat = "vpn"
                elif "printer" in combined:
                    cat = "printer"
                elif "outlook" in combined:
                    cat = "outlook"
                elif "wifi" in combined or "wi-fi" in combined:
                    cat = "wifi"
                elif "teams" in combined:
                    cat = "teams"

                # Count suggested steps in conversation history
                step_keywords = ["please try", "verify the printer", "opening outlook", "restarting teams", "restart your device"]
                step_count = 0
                for t in actual_history:
                    if t.get("role") == "model":
                        text_lower = t.get("text", "").lower()
                        if any(kw in text_lower for kw in step_keywords):
                            step_count += 1

                # Compile failure indicators and check user response
                _FAILURE_INDICATORS = re.compile(
                    r"\b(no|failed|fail|didn't work|did not work|not working|does not work|crashing|still not working|broken|error)\b",
                    re.IGNORECASE,
                )
                user_indicated_failure = bool(_FAILURE_INDICATORS.search(raw_user_msg))

                # Check if a question was already asked in history
                prev_model_responses = [t for t in actual_history if t.get("role") == "model"]
                has_asked_question = len(prev_model_responses) >= 1

                # Check for specific diagnostic evidence
                has_evidence = False
                if cat == "vpn" and any(w in raw_user_msg for w in ["909", "809", "error"]):
                    has_evidence = True
                elif cat == "printer" and any(w in raw_user_msg for w in ["yes", "no", "on", "connected", "offline"]):
                    has_evidence = True
                elif cat == "outlook" and any(w in raw_user_msg for w in ["open", "launch", "crash", "safe", "no"]):
                    has_evidence = True
                elif cat == "wifi" and any(w in raw_user_msg for w in ["909", "809", "not connected", "no internet", "offline"]):
                    has_evidence = True
                elif cat == "teams" and any(w in raw_user_msg for w in ["unable", "connect", "909", "404", "login"]):
                    has_evidence = True

                # Multi-step progression logic
                if step_count == 0:
                    if has_evidence:
                        # Suggest STEP 1
                        if cat == "vpn":
                            msg = (
                                "Error 909 usually indicates a communication issue with the VPN server.\n\n"
                                "Please try:\n"
                                "1. Disconnect VPN.\n"
                                "2. Restart Wi-Fi adapter.\n"
                                "3. Reconnect.\n"
                                "4. Tell me what happens."
                            )
                        elif cat == "printer":
                            msg = "Please verify the printer appears online in Windows and clear any stuck print jobs."
                        elif cat == "outlook":
                            msg = (
                                "Please try opening Outlook in Safe Mode by pressing Windows + R and running:\n\n"
                                "outlook.exe /safe\n\n"
                                "Let me know what happens."
                            )
                        elif cat == "wifi":
                            msg = "Please try restarting your Wi-Fi adapter or checking physical connections."
                        elif cat == "teams":
                            msg = "Please try restarting Teams, clearing the Teams cache, or verifying your internet connection."
                        else:
                            msg = "Please restart your device or application and verify if the issue persists."

                        return json.dumps({
                            "assistant_message": msg,
                            "intent": "GENERAL_SUPPORT",
                            "tool": None,
                            "parameters": {},
                            "confidence": 0.9,
                            "requires_confirmation": False,
                            "action_type": "STEP",
                            "escalation_reason": None
                        })
                    else:
                        # Ask diagnostic question
                        if has_asked_question:
                            if cat == "vpn":
                                msg = "I need a bit more detail. Please check the VPN client window and tell me if you see error 909, 809, or connection timeout."
                            elif cat == "printer":
                                msg = "Please double check the printer power indicator and network link light. Is it on and online?"
                            elif cat == "outlook":
                                msg = "To help diagnose, please check if Outlook is completely unresponsive, crashing on startup, or showing a specific error box."
                            elif cat == "wifi":
                                msg = "I need a bit more information. Are you seeing 'No Internet', 'Connected, No Internet', an error code, or is the Wi-Fi network missing?"
                            elif cat == "teams":
                                msg = "I need a bit more detail. Please describe any error messages or connection issues you see."
                            else:
                                msg = "Please describe the symptoms in more detail, such as any error codes or messages displayed."
                        else:
                            if cat == "vpn":
                                msg = "Do you see an error code?"
                            elif cat == "printer":
                                msg = "Is the printer powered on and connected to the network?"
                            elif cat == "outlook":
                                msg = "Does Outlook show an error or close immediately?"
                            elif cat == "wifi":
                                msg = "Can you describe what you see? Are you unable to connect to any network, or is it a specific SSID?"
                            elif cat == "teams":
                                msg = "Are you experiencing issues with Teams calls, chat, or connection?"
                            else:
                                msg = "Let's troubleshoot this issue. Can you describe what you see?"

                        return json.dumps({
                            "assistant_message": msg,
                            "intent": "GENERAL_SUPPORT",
                            "tool": None,
                            "parameters": {},
                            "confidence": 0.9,
                            "requires_confirmation": False,
                            "action_type": "QUESTION",
                            "escalation_reason": None
                        })

                elif step_count == 1:
                    if user_indicated_failure:
                        # Suggest STEP 2
                        if cat == "vpn":
                            msg = (
                                "Let's try checking your system time. Please verify that your system date and time "
                                "are synchronized automatically. If they are out of sync, the security handshake will fail."
                            )
                        elif cat == "printer":
                            msg = "Let's try restarting the print spooler service. Press Windows + R, type 'services.msc', find 'Print Spooler', and click Restart."
                        elif cat == "outlook":
                            msg = "Let's try repairing the Office installation. Go to Control Panel > Programs and Features, select Microsoft Office, and click Change > Quick Repair."
                        elif cat == "wifi":
                            msg = "Let's try releasing and renewing your IP configuration. Open Command Prompt and run 'ipconfig /release' followed by 'ipconfig /renew'."
                        elif cat == "teams":
                            msg = "Let's try using the Teams Web App (teams.microsoft.com) to check if the connection issue is specific to the desktop client."
                        else:
                            msg = "Please check if there are any pending system updates that need to be installed."

                        return json.dumps({
                            "assistant_message": msg,
                            "intent": "GENERAL_SUPPORT",
                            "tool": None,
                            "parameters": {},
                            "confidence": 0.9,
                            "requires_confirmation": False,
                            "action_type": "STEP",
                            "escalation_reason": None
                        })
                    else:
                        # User didn't report failure, ask if previous step worked
                        return json.dumps({
                            "assistant_message": "Did that troubleshooting step resolve the issue, or is it still not working?",
                            "intent": "GENERAL_SUPPORT",
                            "tool": None,
                            "parameters": {},
                            "confidence": 0.9,
                            "requires_confirmation": False,
                            "action_type": "QUESTION",
                            "escalation_reason": None
                        })

                else:  # step_count >= 2
                    if user_indicated_failure:
                        # Escalate to ticket creation
                        return json.dumps({
                            "assistant_message": "I've tried resolving this but since it failed, let me create a ticket for you.",
                            "intent": "CREATE_TICKET",
                            "tool": "CREATE_TICKET",
                            "parameters": {},
                            "confidence": 0.95,
                            "requires_confirmation": True,
                            "action_type": "QUESTION",
                            "escalation_reason": "EXHAUSTED"
                        })
                    else:
                        # Ask if it works
                        return json.dumps({
                            "assistant_message": "Did that second troubleshooting step work, or are you still experiencing issues?",
                            "intent": "GENERAL_SUPPORT",
                            "tool": None,
                            "parameters": {},
                            "confidence": 0.9,
                            "requires_confirmation": False,
                            "action_type": "QUESTION",
                            "escalation_reason": None
                        })

        elif "tool result" in combined or "status:" in combined or "message:" in combined:
            return "I have successfully processed your request."
        else:
            return "Let's work through this together. First, can you tell me if there are any error messages displayed?"

    def generate_response(self, user_message: str, knowledge_context: Optional[str] = None) -> Any:
        p_l = user_message.lower()
        if "exactly one of these categories" in p_l:
            query_match = re.search(r'query:\s*"(.*?)"', p_l)
            query_part = query_match.group(1) if query_match else p_l

            def has_any(keywords):
                for kw in keywords:
                    if re.search(r'\b' + re.escape(kw) + r'\b', query_part):
                        return True
                return False

            if has_any(["vpn"]): return "VPN"
            if has_any(["password", "unlock"]): return "PASSWORD_RESET"
            if has_any(["outlook", "email", "mail"]): return "OUTLOOK"
            if has_any(["software", "install"]): return "SOFTWARE_INSTALLATION"
            if has_any(["printer", "printing"]): return "PRINTER"
            if has_any(["sap"]): return "SAP"
            if has_any(["teams"]): return "TEAMS"
            if has_any(["onedrive"]): return "ONEDRIVE"
            if has_any(["wifi", "wi-fi", "wireless"]): return "WIFI"
            if has_any(["browser", "chrome", "edge"]): return "BROWSER"
            if has_any(["adobe", "pdf"]): return "ADOBE"
            if has_any(["citrix"]): return "CITRIX"
            if has_any(["bitlocker"]): return "BITLOCKER"
            if has_any(["driver", "drivers"]): return "DRIVERS"
            if has_any(["login", "sign in"]): return "LOGIN"
            if has_any(["windows"]): return "WINDOWS"
            if has_any(["hardware", "keyboard", "monitor", "laptop", "mouse", "docking station", "usb", "peripheral"]): return "HARDWARE"
            if has_any(["network", "switch", "ethernet", "lan", "connectivity"]): return "NETWORK"
            if has_any(["performance", "slow", "sluggish", "lagging", "freezing"]): return "PERFORMANCE"
            if has_any(["office"]): return "OFFICE"
            return "GENERAL"
        return "Let's troubleshoot this issue together. Can you tell me if there are any error messages?"


class OllamaProvider(BaseAIProvider):
    def is_ready(self) -> bool:
        return False
    def verify(self) -> bool:
        return True
    def chat(self, user_message: str, history: Optional[List[dict]] = None) -> str:
        raise NotImplementedError("OllamaProvider: Not implemented.")
    def generate_response(self, user_message: str, knowledge_context: Optional[str] = None) -> Any:
        raise NotImplementedError("OllamaProvider: Not implemented.")


class AzureOpenAIProvider(BaseAIProvider):
    def is_ready(self) -> bool:
        return False
    def verify(self) -> bool:
        return True
    def chat(self, user_message: str, history: Optional[List[dict]] = None) -> str:
        raise NotImplementedError("AzureOpenAIProvider: Not implemented.")
    def generate_response(self, user_message: str, knowledge_context: Optional[str] = None) -> Any:
        raise NotImplementedError("AzureOpenAIProvider: Not implemented.")


class OpenAIProvider(BaseAIProvider):
    def is_ready(self) -> bool:
        return False
    def verify(self) -> bool:
        return True
    def chat(self, user_message: str, history: Optional[List[dict]] = None) -> str:
        raise NotImplementedError("OpenAIProvider: Not implemented.")
    def generate_response(self, user_message: str, knowledge_context: Optional[str] = None) -> Any:
        raise NotImplementedError("OpenAIProvider: Not implemented.")


_provider_lock = threading.Lock()
_active_provider: Optional[BaseAIProvider] = None

def get_ai_provider() -> BaseAIProvider:
    global _active_provider
    if _active_provider is not None:
        return _active_provider

    with _provider_lock:
        if _active_provider is not None:
            return _active_provider

        provider_choice = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

        if provider_choice == "mock":
            logger.info("AIProvider: MockProvider explicitly selected as LLM_PROVIDER.")
            _active_provider = MockProvider()
        elif provider_choice == "ollama":
            _active_provider = OllamaProvider()
        elif provider_choice == "azure":
            _active_provider = AzureOpenAIProvider()
        elif provider_choice == "openai":
            _active_provider = OpenAIProvider()
        elif provider_choice == "gemini":
            try:
                logger.info("AIProvider: Initializing GeminiProvider...")
                gemini = GeminiProvider()
                _active_provider = gemini
                logger.info("AIProvider: GeminiProvider successfully set as active.")
            except Exception as exc:
                logger.error("AIProvider: GeminiProvider initialization failed: %s", exc, exc_info=True)
                raise RuntimeError(
                    f"AIProvider: Gemini is configured as active provider, but initialization failed: {exc}"
                )
        elif provider_choice == "claude":
            try:
                logger.info("AIProvider: Initializing ClaudeProvider...")
                claude = ClaudeProvider()
                _active_provider = claude
                logger.info("AIProvider: ClaudeProvider successfully set as active.")
            except Exception as exc:
                logger.error("AIProvider: ClaudeProvider initialization failed: %s", exc, exc_info=True)
                raise RuntimeError(
                    f"AIProvider: Claude is configured as active provider, but initialization failed: {exc}"
                )
        else:
            raise ValueError(f"AIProvider: Unknown LLM_PROVIDER '{provider_choice}' specified in environment.")

        # Increment provider initialization metric
        try:
            from app.core.metrics import LLM_PROVIDER_INITIALIZATION_TOTAL
            LLM_PROVIDER_INITIALIZATION_TOTAL.inc()
        except Exception as mex:
            logger.warning("Failed to increment LLM provider initialization metric: %s", mex)

        # Visual logging block for the active provider and model
        provider_name = _active_provider.__class__.__name__.replace("Provider", "")
        model_name = getattr(_active_provider, "_model_name", "Mock Model")
        logger.info(
            "\n=================================================\n"
            "Active AI Provider : %s\n"
            "Model              : %s\n"
            "=================================================",
            provider_name, model_name
        )

        return _active_provider

