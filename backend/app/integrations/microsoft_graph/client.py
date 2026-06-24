import os
import time
import logging
import requests
from requests.auth import HTTPBasicAuth

from .graph_client import MicrosoftGraphClientInterface

logger = logging.getLogger("it-agent-backend")

class MicrosoftGraphRealClient(MicrosoftGraphClientInterface):
    is_mock = False

    def __init__(self, tenant_id: str = None, client_id: str = None, client_secret: str = None):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._cached_token = None
        self._token_expires_at = 0

    def _get_headers(self) -> dict:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        token = self._get_oauth_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _get_oauth_token(self) -> str | None:
        # Check cache validity (with 60 seconds safety window)
        if self._cached_token and time.time() < self._token_expires_at - 60:
            return self._cached_token

        logger.info("Microsoft Graph: Fetching Azure AD OAuth Access Token...")
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default"
        }
        
        try:
            response = requests.post(url, data=payload, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                self._cached_token = data.get("access_token")
                self._token_expires_at = time.time() + data.get("expires_in", 3600)
                logger.info("Microsoft Graph OAuth: Token cached successfully")
                return self._cached_token
            else:
                logger.error("Microsoft Graph OAuth: Access token request failed %d: %s", response.status_code, response.text)
        except Exception as e:
            logger.error("Microsoft Graph OAuth: Exception during OAuth call: %s", e)
            
        return None

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.get("headers", {})
        oauth_headers = self._get_headers()
        # Merge headers
        kwargs["headers"] = {**oauth_headers, **headers}
        kwargs["timeout"] = kwargs.get("timeout", 10.0)
        return requests.request(method, url, **kwargs)

    def check_connectivity(self) -> dict:
        import time
        url = "https://graph.microsoft.com/v1.0/users?$top=1"
        start_time = time.time()
        try:
            # Test token retrieval
            token = self._get_oauth_token()
            if not token:
                return {
                    "status": "unhealthy",
                    "latency": time.time() - start_time,
                    "details": "Authentication failed (OAuth token was not retrieved).",
                    "token_expiry": 0
                }
                
            response = self._request("GET", url, timeout=5.0)
            duration = time.time() - start_time
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latency": duration,
                    "details": "Microsoft Graph API connectivity and authentication verified.",
                    "token_expiry": int(self._token_expires_at)
                }
            else:
                return {
                    "status": "unhealthy",
                    "latency": duration,
                    "details": f"API error response {response.status_code}: {response.text}",
                    "token_expiry": int(self._token_expires_at)
                }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "status": "unhealthy",
                "latency": duration,
                "details": f"Network exception check failure: {str(e)}",
                "token_expiry": 0
            }

    # User delegates
    def get_user(self, user_id: str) -> dict:
        from .users import get_user as _get
        return _get(self, user_id)

    def get_user_profile(self, user_id: str) -> dict:
        from .users import get_user_profile as _get_prof
        return _get_prof(self, user_id)

    def get_manager(self, user_id: str) -> dict:
        from .users import get_manager as _get_mgr
        return _get_mgr(self, user_id)

    def get_user_groups(self, user_id: str) -> list:
        from .users import get_user_groups as _get_grps
        return _get_grps(self, user_id)

    # Mailbox delegates
    def get_mailbox_status(self, user_id: str) -> dict:
        from .mailboxes import get_mailbox_status as _get_mb
        return _get_mb(self, user_id)

    def get_mailbox_settings(self, user_id: str) -> dict:
        from .mailboxes import get_mailbox_settings as _get_mb_set
        return _get_mb_set(self, user_id)

    def check_exchange_connectivity(self) -> dict:
        from .mailboxes import check_exchange_connectivity as _check_conn
        return _check_conn(self)

    # License delegates
    def get_assigned_licenses(self, user_id: str) -> list:
        from .licenses import get_assigned_licenses as _get_lics
        return _get_lics(self, user_id)

    def check_office_license(self, user_id: str) -> dict:
        from .licenses import check_office_license as _check_off
        return _check_off(self, user_id)

    def check_exchange_license(self, user_id: str) -> dict:
        from .licenses import check_exchange_license as _check_exch
        return _check_exch(self, user_id)

    # Group delegates
    def get_group_membership(self, group_id: str) -> list:
        from .groups import get_group_membership as _get_memb
        return _get_memb(self, group_id)

    def check_vpn_group(self, user_id: str) -> dict:
        from .groups import check_vpn_group as _check_vpn
        return _check_vpn(self, user_id)

    def check_security_group(self, user_id: str, group_name: str) -> dict:
        from .groups import check_security_group as _check_sec
        return _check_sec(self, user_id, group_name)

    def get_all_users(self) -> list:
        from .users import get_all_users as _get_all
        return _get_all(self)

    def get_all_groups(self) -> list:
        from .groups import get_all_groups as _get_all_grps
        return _get_all_grps(self)
