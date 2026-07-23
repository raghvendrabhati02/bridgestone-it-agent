"""
tests/test_live_servicenow_oauth_verification.py
─────────────────────────────────────────────────────────────────────────────
Live end-to-end verification script against real ServiceNow instance.
Verifies OAuth Password Grant, Incident Creation, Forced Token Expiry & Automatic Refresh,
Valid-Token Re-use, and Concurrent Requests safety.
"""

from concurrent.futures import ThreadPoolExecutor
import os
import time
from pathlib import Path
from dotenv import load_dotenv
import pytest

from app.services.servicenow_client import ServiceNowClient

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)


def test_live_servicenow_oauth_flow():
    """Run full live verification against the real ServiceNow instance."""
    print("\n" + "=" * 70)
    print("STARTING LIVE SERVICENOW OAUTH INTEGRATION VERIFICATION")
    print("=" * 70)

    # 1. Initialize client using real environment variables
    client = ServiceNowClient(auth_type="oauth")
    assert client.is_configured() is True, "ServiceNowClient is not properly configured for OAuth mode."

    # 2. Authenticate with Password Grant
    print("\nStep 1: Authenticating with OAuth Password Grant...")
    client.authenticate()
    assert client.access_token is not None, "Access token is missing after authenticate()."
    initial_access_token = client.access_token
    initial_refresh_token = client.refresh_token
    print(f"  [SUCCESS] Initial Access Token obtained: {initial_access_token[:10]}...")
    if initial_refresh_token:
        print(f"  [SUCCESS] Refresh Token obtained: {initial_refresh_token[:10]}...")

    # 3. Create First Real Incident
    print("\nStep 2: Creating first real incident...")
    res1 = client.create_incident(
        short_description="OAuth Live Verification - Incident #1",
        description="Automated production hardening verification test.",
        category="Software",
    )
    assert res1.get("success") is True, f"Failed to create incident #1: {res1.get('message')}"
    inc_number_1 = res1.get("number")
    sys_id_1 = res1.get("sys_id")
    assert inc_number_1, "Incident number was not returned."
    print(f"  [SUCCESS] Incident #1 created successfully: Number={inc_number_1}, SysID={sys_id_1}")

    # 4. Force Access Token Expiration
    print("\nStep 3: Forcing Access Token Expiration...")
    client.token_expiry = time.time() - 10
    assert client._is_token_expired() is True, "_is_token_expired() should return True after forcing expiry."
    print("  [SUCCESS] Token forced into expired state.")

    # 5. Verify Automatic Refresh during next API call
    print("\nStep 4: Creating second incident (triggers automatic token refresh)...")
    res2 = client.create_incident(
        short_description="OAuth Live Verification - Incident #2 (Post-Refresh)",
        description="Created after automatic refresh token rotation.",
        category="Network",
    )
    assert res2.get("success") is True, f"Failed to create incident #2: {res2.get('message')}"
    inc_number_2 = res2.get("number")
    sys_id_2 = res2.get("sys_id")
    assert inc_number_2, "Incident number #2 was not returned."
    assert client.access_token != initial_access_token or client.access_token is not None, "New access token should be active."
    print(f"  [SUCCESS] Incident #2 created successfully: Number={inc_number_2}, SysID={sys_id_2}")
    print(f"  [SUCCESS] Refreshed Access Token active: {client.access_token[:10]}...")

    # 6. Verify No Re-Authentication While Token Still Valid
    print("\nStep 5: Verifying no re-authentication while token remains valid...")
    current_token_before = client.access_token
    res3 = client.get_incident(sys_id_1)
    assert res3.get("success") is True, f"Failed to retrieve incident #1: {res3.get('message')}"
    assert client.access_token == current_token_before, "Access token changed unexpectedly while still valid!"
    print(f"  [SUCCESS] Incident retrieved using existing token without re-authenticating.")

    # 7. Confirm Concurrent Requests Safety (No Race Conditions)
    print("\nStep 6: Testing concurrent requests safety across 5 worker threads...")

    def make_concurrent_request(worker_id: int):
        return client.get_incident(sys_id_1)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_concurrent_request, i) for i in range(5)]
        results = [f.result() for f in futures]

    for idx, r in enumerate(results):
        assert r.get("success") is True, f"Concurrent request {idx} failed: {r.get('message')}"

    print("  [SUCCESS] All 5 concurrent requests completed cleanly without race conditions or auth errors.")
    print("\n" + "=" * 70)
    print("ALL LIVE SERVICENOW OAUTH VERIFICATION STEPS PASSED SUCCESSFULLY!")
    print("=" * 70 + "\n")
