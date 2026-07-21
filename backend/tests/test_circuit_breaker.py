import os
import pytest
import time
from unittest.mock import patch, MagicMock

# Mock environment variables before importing GeminiProvider
with patch.dict(os.environ, {"GEMINI_API_KEY": "mock_key_for_test", "GEMINI_MODEL": "gemini-3.5-flash"}):
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        from app.services.ai_provider import GeminiProvider

def test_circuit_breaker_flow():
    # Make sure env is patched when creating provider and during execution
    with patch.dict(os.environ, {"GEMINI_API_KEY": "mock_key_for_test", "GEMINI_MODEL": "gemini-3.5-flash"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            provider = GeminiProvider()
            
        provider._circuit_failure_threshold = 2
        provider._circuit_recovery_timeout = 0.5
        
        call_count = 0
        def failing_api(model_name):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Simulated 503 Service Unavailable")
            
        # Execute and exhaust retries (max_retries=0 to make it fast)
        with pytest.raises(Exception):
            provider._execute_with_retry(lambda: failing_api("gemini-3.5-flash"), max_retries=0)
            
        assert provider._circuit_state == "CLOSED"
        assert provider._circuit_failures == 1
        
        # Second failure should trip the circuit to OPEN
        with pytest.raises(Exception):
            provider._execute_with_retry(lambda: failing_api("gemini-3.5-flash"), max_retries=0)
            
        assert provider._circuit_state == "OPEN"
        assert provider._circuit_failures == 2
        
        # Subsequent calls should immediately fail with Circuit Breaker OPEN without calling the API
        with pytest.raises(RuntimeError) as exc_info:
            provider._execute_with_retry(lambda: failing_api("gemini-3.5-flash"), max_retries=0)
        assert "Circuit is OPEN" in str(exc_info.value)
        assert call_count == 2  # API call was bypassed!
        
        # Sleep to exceed recovery timeout
        time.sleep(0.6)
        
        # Next call should attempt a HALF_OPEN test
        # Let's make it succeed this time
        def succeeding_api(model_name):
            return "SUCCESS"
            
        res = provider._execute_with_retry(lambda: succeeding_api("gemini-3.5-flash"), max_retries=0)
        assert res == "SUCCESS"
        assert provider._circuit_state == "CLOSED"
        assert provider._circuit_failures == 0
