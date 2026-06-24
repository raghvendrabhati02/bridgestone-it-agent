from abc import ABC, abstractmethod
import time
import logging
import requests

logger = logging.getLogger("it-agent-backend")

class EntraIdClientInterface(ABC):
    @abstractmethod
    def get_user(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def get_user_profile(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def get_manager(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def get_department(self, user_id: str) -> str:
        pass

    @abstractmethod
    def get_user_groups(self, user_id: str) -> list:
        pass

    @abstractmethod
    def check_group_membership(self, user_id: str, group_name_or_id: str) -> bool:
        pass

    @abstractmethod
    def get_group_details(self, group_id: str) -> dict:
        pass

    @abstractmethod
    def check_vpn_access(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def check_application_access(self, user_id: str, app_name: str) -> dict:
        pass

    @abstractmethod
    def check_security_group_access(self, user_id: str, group_name: str) -> dict:
        pass

    @abstractmethod
    def get_user_roles(self, user_id: str) -> list:
        pass

    @abstractmethod
    def check_admin_role(self, user_id: str) -> bool:
        pass

    @abstractmethod
    def check_manager_role(self, user_id: str) -> bool:
        pass

    @abstractmethod
    def check_connectivity(self) -> dict:
        pass

    @abstractmethod
    def get_all_users(self) -> list:
        pass

    @abstractmethod
    def get_all_groups(self) -> list:
        pass

    @abstractmethod
    def get_monitoring_stats(self) -> dict:
        pass


class EntraIdMockClient(EntraIdClientInterface):
    is_mock = True

    def __init__(self):
        # Local stats counters
        self.group_checks = 0
        self.access_checks = 0
        self.role_checks = 0

        # Seeded data
        self.users = {
            "entra-user-12345": {
                "id": "entra-user-12345",
                "displayName": "Standard Employee",
                "mail": "employee@bridgestone.com",
                "userPrincipalName": "employee",
                "jobTitle": "Support Specialist",
                "department": "IT Service Desk"
            },
            "entra-user-manager": {
                "id": "entra-user-manager",
                "displayName": "Test Manager",
                "mail": "manager@bridgestone.com",
                "userPrincipalName": "manager",
                "jobTitle": "Service Desk Manager",
                "department": "IT Operations"
            },
            "entra-user-admin": {
                "id": "entra-user-admin",
                "displayName": "System Admin",
                "mail": "admin@bridgestone.com",
                "userPrincipalName": "admin",
                "jobTitle": "IT Administrator",
                "department": "Infrastructure"
            }
        }

        self.managers = {
            "entra-user-12345": "entra-user-manager",
            "entra-user-manager": "entra-user-admin"
        }

        self.user_groups = {
            "entra-user-12345": [
                {"id": "egrp-1", "displayName": "Domain Users", "description": "Standard domain users"},
                {"id": "egrp-2", "displayName": "VPN Users", "description": "Users allowed to connect to corporate VPN"}
            ],
            "entra-user-manager": [
                {"id": "egrp-1", "displayName": "Domain Users", "description": "Standard domain users"},
                {"id": "egrp-3", "displayName": "Domain Managers", "description": "Managers"}
            ],
            "entra-user-admin": [
                {"id": "egrp-1", "displayName": "Domain Users", "description": "Standard domain users"},
                {"id": "egrp-4", "displayName": "Domain Admins", "description": "Administrators"}
            ]
        }

    def _resolve_user(self, user_id: str) -> dict | None:
        if user_id in self.users:
            return self.users[user_id]
        for u in self.users.values():
            if u["userPrincipalName"].lower() == user_id.lower() or u["mail"].lower() == user_id.lower():
                return u
        # Return fallback mock employee for dynamic verification test accounts
        if "disabled" in user_id.lower():
            return {
                "id": "entra-user-disabled",
                "displayName": "Disabled Employee",
                "mail": f"{user_id}@bridgestone.com",
                "userPrincipalName": user_id,
                "jobTitle": "Unassigned",
                "department": "Temporary"
            }
        return {
            "id": f"entra-user-{hash(user_id) % 100000}",
            "displayName": user_id.capitalize(),
            "mail": f"{user_id}@bridgestone.com",
            "userPrincipalName": user_id,
            "jobTitle": "Employee",
            "department": "IT Operations"
        }

    def get_user(self, user_id: str) -> dict:
        from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
        start = time.time()
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_user").inc()
        except Exception:
            pass
        logger.info("EntraIdMockClient: get_user %s", user_id)
        u = self._resolve_user(user_id)
        if not u:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_user", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"User {user_id} not found.")
        try:
            AD_LATENCY_SECONDS.labels(operation="get_user").observe(time.time() - start)
        except Exception:
            pass
        return u

    def get_user_profile(self, user_id: str) -> dict:
        from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
        start = time.time()
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_user_profile").inc()
        except Exception:
            pass
        logger.info("EntraIdMockClient: get_user_profile %s", user_id)
        try:
            res = self.get_user(user_id)
            try:
                AD_LATENCY_SECONDS.labels(operation="get_user_profile").observe(time.time() - start)
            except Exception:
                pass
            return res
        except Exception as e:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_user_profile", error_type=type(e).__name__).inc()
            except Exception:
                pass
            raise e

    def get_manager(self, user_id: str) -> dict:
        from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
        start = time.time()
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_manager").inc()
        except Exception:
            pass
        logger.info("EntraIdMockClient: get_manager of %s", user_id)
        try:
            user = self.get_user(user_id)
            mgr_id = self.managers.get(user["id"])
            if mgr_id and mgr_id in self.users:
                try:
                    AD_LATENCY_SECONDS.labels(operation="get_manager").observe(time.time() - start)
                except Exception:
                    pass
                return self.users[mgr_id]
            raise KeyError(f"Manager for user {user_id} not found.")
        except Exception as e:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_manager", error_type=type(e).__name__).inc()
            except Exception:
                pass
            raise e

    def get_department(self, user_id: str) -> str:
        from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
        start = time.time()
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_department").inc()
        except Exception:
            pass
        logger.info("EntraIdMockClient: get_department of %s", user_id)
        try:
            user = self.get_user(user_id)
            try:
                AD_LATENCY_SECONDS.labels(operation="get_department").observe(time.time() - start)
            except Exception:
                pass
            return user.get("department", "Unknown")
        except Exception as e:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_department", error_type=type(e).__name__).inc()
            except Exception:
                pass
            return "Unknown"

    def get_user_groups(self, user_id: str) -> list:
        from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
        start = time.time()
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_user_groups").inc()
        except Exception:
            pass
        logger.info("EntraIdMockClient: get_user_groups of %s", user_id)
        try:
            user = self.get_user(user_id)
            uid = user["id"]
            try:
                AD_LATENCY_SECONDS.labels(operation="get_user_groups").observe(time.time() - start)
            except Exception:
                pass
            if uid not in self.user_groups:
                if "disabled" in user["userPrincipalName"].lower():
                    return [{"id": "egrp-1", "displayName": "Domain Users", "description": "Standard domain users"}]
                return [
                    {"id": "egrp-1", "displayName": "Domain Users", "description": "Standard domain users"},
                    {"id": "egrp-2", "displayName": "VPN Users", "description": "Users allowed to connect to corporate VPN"}
                ]
            return self.user_groups.get(uid, [])
        except Exception as e:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_user_groups", error_type=type(e).__name__).inc()
            except Exception:
                pass
            return []

    def check_group_membership(self, user_id: str, group_name_or_id: str) -> bool:
        from app.core.metrics import GROUP_CHECKS_TOTAL
        try:
            GROUP_CHECKS_TOTAL.inc()
        except Exception:
            pass
        self.group_checks += 1
        groups = self.get_user_groups(user_id)
        return any(g.get("displayName") == group_name_or_id or g.get("id") == group_name_or_id for g in groups)

    def get_group_details(self, group_id: str) -> dict:
        from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
        start = time.time()
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_group_details").inc()
        except Exception:
            pass
        logger.info("EntraIdMockClient: get_group_details for %s", group_id)
        for grps in self.user_groups.values():
            for g in grps:
                if g["id"] == group_id:
                    try:
                        AD_LATENCY_SECONDS.labels(operation="get_group_details").observe(time.time() - start)
                    except Exception:
                        pass
                    return g
        try:
            AD_FAILURES_TOTAL.labels(operation="get_group_details", error_type="KeyError").inc()
        except Exception:
            pass
        raise KeyError(f"Group {group_id} not found.")

    def check_vpn_access(self, user_id: str) -> dict:
        from app.core.metrics import ACCESS_CHECKS_TOTAL
        try:
            ACCESS_CHECKS_TOTAL.inc()
        except Exception:
            pass
        self.access_checks += 1
        user = self.get_user(user_id)
        has_access = self.check_group_membership(user["id"], "VPN Users")
        return {
            "user_id": user_id,
            "target": "VPN",
            "allowed": has_access,
            "details": "User is a member of the 'VPN Users' Entra group." if has_access else "User is not a member of 'VPN Users' Entra group."
        }

    def check_application_access(self, user_id: str, app_name: str) -> dict:
        from app.core.metrics import ACCESS_CHECKS_TOTAL
        try:
            ACCESS_CHECKS_TOTAL.inc()
        except Exception:
            pass
        self.access_checks += 1
        user = self.get_user(user_id)
        has_access = self.check_group_membership(user["id"], "Domain Users")
        return {
            "user_id": user_id,
            "target": app_name,
            "allowed": has_access,
            "details": f"User is authorized to access {app_name}." if has_access else f"User is blocked from accessing {app_name}."
        }

    def check_security_group_access(self, user_id: str, group_name: str) -> dict:
        from app.core.metrics import ACCESS_CHECKS_TOTAL
        try:
            ACCESS_CHECKS_TOTAL.inc()
        except Exception:
            pass
        self.access_checks += 1
        user = self.get_user(user_id)
        is_member = self.check_group_membership(user["id"], group_name)
        return {
            "user_id": user_id,
            "target": group_name,
            "allowed": is_member,
            "details": f"User is a member of security group '{group_name}'." if is_member else f"User is not a member of security group '{group_name}'."
        }

    def get_user_roles(self, user_id: str) -> list:
        self.role_checks += 1
        user = self.get_user(user_id)
        roles = []
        if self.check_group_membership(user["id"], "Domain Admins"):
            roles.append("ADMIN")
        if self.check_group_membership(user["id"], "Domain Managers"):
            roles.append("MANAGER")
        roles.append("EMPLOYEE")
        return roles

    def check_admin_role(self, user_id: str) -> bool:
        return "ADMIN" in self.get_user_roles(user_id)

    def check_manager_role(self, user_id: str) -> bool:
        roles = self.get_user_roles(user_id)
        return "MANAGER" in roles or "ADMIN" in roles

    def check_connectivity(self) -> dict:
        return {
            "status": "healthy",
            "latency": 0.001,
            "details": "Mock Mode active.",
            "token_expiry": 9999999999
        }

    def get_all_users(self) -> list:
        from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
        start = time.time()
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_all_users").inc()
        except Exception:
            pass
        logger.info("EntraIdMockClient: Fetching all mock users")
        res = list(self.users.values())
        try:
            AD_LATENCY_SECONDS.labels(operation="get_all_users").observe(time.time() - start)
        except Exception:
            pass
        return res

    def get_all_groups(self) -> list:
        from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
        start = time.time()
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_all_groups").inc()
        except Exception:
            pass
        logger.info("EntraIdMockClient: Fetching all mock groups")
        seen = set()
        unique_groups = []
        for groups in self.user_groups.values():
            for g in groups:
                if g["id"] not in seen:
                    seen.add(g["id"])
                    unique_groups.append(g)
        try:
            AD_LATENCY_SECONDS.labels(operation="get_all_groups").observe(time.time() - start)
        except Exception:
            pass
        return unique_groups

    def get_monitoring_stats(self) -> dict:
        return {
            "status": "healthy",
            "latency_ms": 1.0,
            "total_users": len(self.users),
            "total_groups": len(self.get_all_groups()),
            "group_membership_checks": self.group_checks,
            "access_validation_checks": self.access_checks,
            "role_assignment_checks": self.role_checks
        }


class EntraIdRealClient(EntraIdClientInterface):
    is_mock = False

    def __init__(self, tenant_id: str = None, client_id: str = None, client_secret: str = None):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._cached_token = None
        self._token_expires_at = 0
        
        # Real client stats tracking (in-memory)
        self.group_checks = 0
        self.access_checks = 0
        self.role_checks = 0

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
        if self._cached_token and time.time() < self._token_expires_at - 60:
            return self._cached_token

        logger.info("Entra ID OAuth: Fetching Azure AD Access Token...")
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
                logger.info("Entra ID OAuth: Token cached successfully")
                return self._cached_token
            else:
                logger.error("Entra ID OAuth: Access token request failed %d: %s", response.status_code, response.text)
        except Exception as e:
            logger.error("Entra ID OAuth: Exception during OAuth call: %s", e)
            
        return None

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.get("headers", {})
        oauth_headers = self._get_headers()
        kwargs["headers"] = {**oauth_headers, **headers}
        kwargs["timeout"] = kwargs.get("timeout", 10.0)
        return requests.request(method, url, **kwargs)

    def check_connectivity(self) -> dict:
        url = "https://graph.microsoft.com/v1.0/users?$top=1"
        start_time = time.time()
        try:
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
                    "details": "Azure AD / Entra ID connection verified.",
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

    # Delegation delegates
    def get_user(self, user_id: str) -> dict:
        from .users import get_user as _get
        return _get(self, user_id)

    def get_user_profile(self, user_id: str) -> dict:
        from .users import get_user_profile as _get_prof
        return _get_prof(self, user_id)

    def get_manager(self, user_id: str) -> dict:
        from .users import get_manager as _get_mgr
        return _get_mgr(self, user_id)

    def get_department(self, user_id: str) -> str:
        from .users import get_department as _get_dept
        return _get_dept(self, user_id)

    def get_user_groups(self, user_id: str) -> list:
        from .groups import get_user_groups as _get_grps
        return _get_grps(self, user_id)

    def check_group_membership(self, user_id: str, group_name_or_id: str) -> bool:
        self.group_checks += 1
        from .groups import check_group_membership as _check_grp
        return _check_grp(self, user_id, group_name_or_id)

    def get_group_details(self, group_id: str) -> dict:
        from .groups import get_group_details as _get_gdet
        return _get_gdet(self, group_id)

    def check_vpn_access(self, user_id: str) -> dict:
        self.access_checks += 1
        from .access import check_vpn_access as _check_vpn
        return _check_vpn(self, user_id)

    def check_application_access(self, user_id: str, app_name: str) -> dict:
        self.access_checks += 1
        from .access import check_application_access as _check_app
        return _check_app(self, user_id, app_name)

    def check_security_group_access(self, user_id: str, group_name: str) -> dict:
        self.access_checks += 1
        from .access import check_security_group_access as _check_sec
        return _check_sec(self, user_id, group_name)

    def get_user_roles(self, user_id: str) -> list:
        self.role_checks += 1
        from .roles import get_user_roles as _get_roles
        return _get_roles(self, user_id)

    def check_admin_role(self, user_id: str) -> bool:
        from .roles import check_admin_role as _check_adm
        return _check_adm(self, user_id)

    def check_manager_role(self, user_id: str) -> bool:
        from .roles import check_manager_role as _check_mgr
        return _check_mgr(self, user_id)

    def get_all_users(self) -> list:
        from .users import get_all_users as _get_all
        return _get_all(self)

    def get_all_groups(self) -> list:
        from .groups import get_all_groups as _get_all_grps
        return _get_all_grps(self)

    def get_monitoring_stats(self) -> dict:
        conn = self.check_connectivity()
        return {
            "status": conn.get("status", "unhealthy"),
            "latency_ms": conn.get("latency", 0.0) * 1000,
            "total_users": len(self.get_all_users()),
            "total_groups": len(self.get_all_groups()),
            "group_membership_checks": self.group_checks,
            "access_validation_checks": self.access_checks,
            "role_assignment_checks": self.role_checks
        }
