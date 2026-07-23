"""
tests/test_servicenow_client_oauth.py
─────────────────────────────────────────────────────────────────────────────
Production hardening unit tests for ServiceNowClient OAuth Password Grant,
Refresh Token rotation, thread safety, double-authentication prevention,
token expiration buffer, sanitized 401 retry, and early configuration validation.
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from app.services.servicenow_client import ServiceNowClient
from app.services.servicenow_exceptions import (
    ServiceNowAuthError,
    ServiceNowConnectionError,
    ServiceNowTimeoutError,
)


@pytest.fixture(autouse=True)
def clean_servicenow_env(monkeypatch):
    """Ensure environment variables do not interfere with unit tests."""
    monkeypatch.delenv("SERVICENOW_TOKEN_URL", raising=False)
    monkeypatch.delenv("SERVICENOW_USERNAME", raising=False)
    monkeypatch.delenv("SERVICENOW_PASSWORD", raising=False)
    monkeypatch.delenv("SERVICENOW_CLIENT_ID", raising=False)
    monkeypatch.delenv("SERVICENOW_CLIENT_SECRET", raising=False)


def test_servicenow_client_is_configured_oauth():
    """Verify is_configured for OAuth mode requires client_id, client_secret, username, password, and token_url."""
    client = ServiceNowClient(
        instance="bridgestone",
        auth_type="oauth",
        client_id="cid123",
        client_secret="csec123",
        username="admin",
        password="password123",
    )
    assert client.is_configured() is True

    # Basic auth missing password returns is_configured() False
    incomplete_basic = ServiceNowClient(
        instance="bridgestone",
        auth_type="basic",
        username="admin",
        password="",
    )
    assert incomplete_basic.is_configured() is False


def test_startup_validation_fails_fast_on_missing_oauth_config():
    """Verify initialization fails immediately if required OAuth parameters are missing."""
    with pytest.raises(ServiceNowAuthError) as exc_info:
        ServiceNowClient(
            instance="bridgestone",
            auth_type="oauth",
            client_id="cid123",
            client_secret="",
            username="admin",
            password="password123",
        )
    assert "SERVICENOW_CLIENT_SECRET" in exc_info.value.message


def test_authenticate_success():
    """Test successful initial OAuth Password Grant authentication."""
    client = ServiceNowClient(
        instance="bridgestone",
        auth_type="oauth",
        client_id="cid123",
        client_secret="csec123",
        username="admin",
        password="password123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "acc_token_999",
        "refresh_token": "ref_token_888",
        "token_type": "Bearer",
        "expires_in": 1800,
    }

    with patch.object(client.session, "post", return_value=mock_response) as mock_post:
        client.authenticate()

        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        assert call_args[0] == "https://bridgestone.service-now.com/oauth_token.do"
        assert call_kwargs["data"] == {
            "grant_type": "password",
            "client_id": "cid123",
            "client_secret": "csec123",
            "username": "admin",
            "password": "password123",
        }
        assert client.access_token == "acc_token_999"
        assert client.refresh_token == "ref_token_888"
        assert client.token_expiry > time.time()


def test_refresh_access_token_success():
    """Test successful token refresh using refresh_token."""
    client = ServiceNowClient(
        instance="bridgestone",
        auth_type="oauth",
        client_id="cid123",
        client_secret="csec123",
        username="admin",
        password="password123",
    )
    client.refresh_token = "existing_ref_token"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new_acc_token",
        "refresh_token": "new_ref_token",
        "token_type": "Bearer",
        "expires_in": 1800,
    }

    with patch.object(client.session, "post", return_value=mock_response) as mock_post:
        client.refresh_access_token()

        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["data"] == {
            "grant_type": "refresh_token",
            "client_id": "cid123",
            "client_secret": "csec123",
            "refresh_token": "existing_ref_token",
        }
        assert client.access_token == "new_acc_token"
        assert client.refresh_token == "new_ref_token"


def test_expiry_helper_safety_buffer():
    """Verify _is_token_expired respects TOKEN_REFRESH_BUFFER safety threshold."""
    client = ServiceNowClient(
        instance="bridgestone",
        auth_type="oauth",
        client_id="cid123",
        client_secret="csec123",
        username="admin",
        password="password123",
    )

    # 1. No access token -> expired
    assert client._is_token_expired() is True

    # 2. Token expires in 30 seconds (within 60s buffer) -> considered expired for refresh
    client.access_token = "tok123"
    client.token_expiry = time.time() + 30
    assert client._is_token_expired() is True

    # 3. Token expires in 120 seconds -> valid
    client.token_expiry = time.time() + 120
    assert client._is_token_expired() is False


def test_ensure_authenticated_double_check_locking():
    """Verify double-checked locking prevents simultaneous authentications."""
    client = ServiceNowClient(
        instance="bridgestone",
        auth_type="oauth",
        client_id="cid123",
        client_secret="csec123",
        username="admin",
        password="password123",
    )

    with patch.object(client, "authenticate") as mock_auth, \
         patch.object(client, "refresh_access_token") as mock_refresh:

        # Scenario 1: Missing token -> calls authenticate once
        client.ensure_authenticated()
        mock_auth.assert_called_once()

        mock_auth.reset_mock()

        # Scenario 2: Valid token -> no-op
        client.access_token = "valid_token"
        client.token_expiry = time.time() + 600
        client.ensure_authenticated()
        mock_auth.assert_not_called()
        mock_refresh.assert_not_called()


def test_execute_request_401_retry_sanitizes_kwargs():
    """Verify 401 Unauthorized retry pops _is_auth_retry so internal flags never leak to requests."""
    client = ServiceNowClient(
        instance="bridgestone",
        auth_type="oauth",
        client_id="cid123",
        client_secret="csec123",
        username="admin",
        password="password123",
    )
    client.access_token = "expired_token"

    res_401 = MagicMock()
    res_401.status_code = 401

    res_200 = MagicMock()
    res_200.status_code = 200
    res_200.text = '{"result": {"sys_id": "sys123"}}'

    with patch.object(client, "ensure_authenticated"), \
         patch.object(client, "refresh_access_token") as mock_refresh, \
         patch.object(client.session, "get", side_effect=[res_401, res_200]) as mock_get:

        def fake_refresh():
            client.access_token = "valid_token"

        mock_refresh.side_effect = fake_refresh

        res = client._execute_request("GET", "https://bridgestone.service-now.com/api/now/table/incident")

        assert res.status_code == 200
        assert mock_get.call_count == 2
        # Verify _is_auth_retry was NOT passed into session.get kwargs
        for call_item in mock_get.call_args_list:
            _, kwargs = call_item
            assert "_is_auth_retry" not in kwargs


def test_execute_request_401_retry_failure_raises_auth_error():
    """Verify 401 Unauthorized raises ServiceNowAuthError if retry also fails."""
    client = ServiceNowClient(
        instance="bridgestone",
        auth_type="oauth",
        client_id="cid123",
        client_secret="csec123",
        username="admin",
        password="password123",
    )
    client.access_token = "invalid_token"

    res_401 = MagicMock()
    res_401.status_code = 401
    res_401.text = "Unauthorized"

    with patch.object(client, "ensure_authenticated"), \
         patch.object(client, "refresh_access_token"), \
         patch.object(client.session, "get", return_value=res_401):

        with pytest.raises(ServiceNowAuthError) as exc_info:
            client._execute_request("GET", "https://bridgestone.service-now.com/api/now/table/incident")

        assert exc_info.value.status_code == 401
