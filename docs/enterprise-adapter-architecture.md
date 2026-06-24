# Enterprise Adapter & Audit Logging Architecture

This document describes the design, class structure, data schemas, and future production integration path for the Enterprise Adapter Layer and the Audit Logging Framework implemented in the Bridgestone IT Agent.

---

## 1. Enterprise Adapter Layer

The Enterprise Adapter Layer decouples the agent's graph and service layers from direct API implementations of external systems. All external system communication passes through concrete implementations of the [BaseAdapter](file:///c:/Projects/it-agent/backend/app/adapters/base_adapter.py) interface.

### Class Diagram / Architecture Workflow

```mermaid
graph TD
    subgraph Service & Graph Layer
        GraphNodes[Graph Nodes / Services]
    end

    subgraph Adapter Interface
        Base[BaseAdapter]
    end

    subgraph Concrete Adapters
        SN[ServiceNowAdapter]
        AD[ActiveDirectoryAdapter]
        MS[MicrosoftGraphAdapter]
        VPN[VPNAdapter]
    end

    subgraph External Systems
        SN_API[(ServiceNow REST API)]
        AD_API[(LDAP / Active Directory)]
        MS_API[(Microsoft Graph API)]
        VPN_API[(Cisco/PaloAlto VPN Gateways)]
    end

    GraphNodes -->|Execute Action| Base
    Base <|-- SN
    Base <|-- AD
    Base <|-- MS
    Base <|-- VPN

    SN -->|REST Call| SN_API
    AD -->|LDAP Query| AD_API
    MS -->|Graph API| MS_API
    VPN -->|SSH / API Call| VPN_API
```

### Adapter Signatures and Methods

#### Base Interface: [BaseAdapter](file:///c:/Projects/it-agent/backend/app/adapters/base_adapter.py)
* **`connect(self) -> bool`**: Establishes a session or authenticates with the remote service.
* **`health_check(self) -> bool`**: Performs a quick status ping to verify remote service availability.
* **`execute(self, action: str, **kwargs) -> any`**: Unified dispatch method to run actions on the adapter.
* **`disconnect(self) -> bool`**: Tears down connections and cleans up active sessions.

#### ServiceNow Adapter: [ServiceNowAdapter](file:///c:/Projects/it-agent/backend/app/adapters/servicenow_adapter.py)
* **Purpose**: Integrates with ServiceNow for incident logging and service request fulfillment.
* **Key Actions**:
  * `create_incident(category: str, description: str, assignment_group: str) -> dict`
  * `create_service_request(category: str, description: str, action_type: str) -> dict`
  * `get_incident(sys_id: str) -> dict`
  * `update_incident(sys_id: str, updates: dict) -> dict`
* **Response Schema**:
  ```json
  {
    "sys_id": "mock-sys-id-...",
    "number": "INC0012345" or "SR0012345",
    "status": "New" or "Opened",
    "description": "...",
    "assignment_group": "..."
  }
  ```

#### Microsoft Graph Adapter: [MicrosoftGraphAdapter](file:///c:/Projects/it-agent/backend/app/adapters/microsoft_graph_adapter.py)
* **Purpose**: Fetches Microsoft 365 profiles, licenses, and Exchange mailbox statuses.
* **Key Actions**:
  * `get_user_profile() -> dict`
  * `get_user_groups() -> list`
  * `get_mailbox_status() -> dict`
  * `check_license_status() -> dict`
* **Response Schema (Profile)**:
  ```json
  {
    "displayName": "Test Employee",
    "mail": "employee@bridgestone.com",
    "userPrincipalName": "employee@bridgestone.com",
    "id": "graph-user-12345"
  }
  ```

#### Active Directory Adapter: [ActiveDirectoryAdapter](file:///c:/Projects/it-agent/backend/app/adapters/active_directory_adapter.py)
* **Purpose**: Inspects and updates domain account state, lockouts, and security group memberships.
* **Key Actions**:
  * `check_user_access(username: str) -> dict`
  * `get_group_membership(username: str) -> list`
  * `unlock_account(username: str) -> dict`
  * `reset_password_request(username: str) -> dict`
* **Response Schema (Account check)**:
  ```json
  {
    "username": "disabled_user",
    "status": "DISABLED"
  }
  ```

#### VPN Adapter: [VPNAdapter](file:///c:/Projects/it-agent/backend/app/adapters/vpn_adapter.py)
* **Purpose**: Diagnostic queries against virtual private network gateways.
* **Key Actions**:
  * `check_gateway_status() -> dict`
  * `check_user_vpn_access(username: str) -> dict`
  * `create_access_restoration_request(username: str) -> dict`
* **Response Schema (Gateway check)**:
  ```json
  {
    "vpn_gateway": "ONLINE",
    "gateway_ip": "172.16.254.1",
    "load_factor": "45%",
    "latency_ms": 18,
    "status": "HEALTHY"
  }
  ```

---

## 2. Audit Logging Framework

The Audit Logging Framework provides structured event persistence for auditing agent activity, tracking approval actions, and recording internal graph agent traces. The implementation resides in [`audit_service.py`](file:///c:/Projects/it-agent/backend/app/services/audit_service.py).

### Schema Mapping (In-Memory Database representation)

#### Audit Logs (`audit_logs_db`)
Tracks the end-to-end user chat turns and corresponding agent outcomes.
* `timestamp` (str - ISO DateTime)
* `session_id` (str)
* `user_message` (str)
* `category` (str)
* `decision` (str)
* `approval_status` (str)
* `recommended_action` (str)
* `action_result` (dict)
* `ticket_id` (str)
* `servicenow_id` (str)

#### Action History (`action_history_db`)
Maintains a log of actions executed by the Action Agent.
* `request_id` (str)
* `action_type` (str)
* `status` (str - "PENDING", "SUCCESS", "FAILED")
* `created_at` (str - ISO DateTime)
* `approved_by_user` (bool)
* `servicenow_id` (str)

#### Approval History (`approval_history_db`)
Records status changes in the action approval lifecycle.
* `session_id` (str)
* `recommended_action` (str)
* `approval_status` (str - "PENDING", "APPROVED", "REJECTED")
* `timestamp` (str - ISO DateTime)

#### Agent Traces (`agent_traces_db`)
Captures internal developer logs and output snapshots from individual LangGraph nodes.
* `session_id` (str)
* `agent_name` (str - e.g., "Intent Agent", "Tool Agent")
* `output` (dict)
* `timestamp` (str - ISO DateTime)

---

## 3. Future Integration and Production Mapping

To replace the adapter mock implementations with real enterprise endpoints, execute the following mappings:

### ServiceNow REST API
* **Endpoint**: `https://{instance}.service-now.com/api/now/table/incident`
* **Protocol**: HTTPS REST (Basic Auth or OAuth 2.0).
* **Mapping**:
  * Send a `POST` request with JSON request body mapping the category, description, and assignment group to ServiceNow table columns:
    ```json
    {
      "category": "network",
      "short_description": "VPN access disabled for user",
      "assignment_group": "VPN Support"
    }
    ```

### Microsoft Graph API
* **Endpoint**: `https://graph.microsoft.com/v1.0`
* **Protocol**: REST with Bearer Token (Azure Active Directory OAuth client credentials flow).
* **Mapping**:
  * `get_user_profile()` maps to `GET /users/{user-id}`
  * `get_mailbox_status()` maps to `GET /users/{user-id}/mailboxSettings` or querying Exchange Admin center endpoints.
  * `check_license_status()` maps to `GET /users/{user-id}/licenseDetails`

### Active Directory (LDAP / PowerShell Web Access)
* **Endpoint**: Internal LDAP servers (`ldaps://ad.bridgestone.local:636`) or Microsoft Active Directory Web Services (ADWS).
* **Protocol**: LDAPS (LDAP over SSL) using standard directory bind.
* **Mapping**:
  * Check account lock status using LDAP queries for attribute `userAccountControl` and `lockoutTime`.
  * Unlock account: Execute an LDAP modify operation setting `lockoutTime` to `0`.

### VPN Gateways (Palo Alto GlobalProtect / Cisco ASA API)
* **Endpoint**: Palo Alto XML API or Cisco ASA REST API endpoints.
* **Protocol**: HTTPS REST or SSH execution.
* **Mapping**:
  * Run VPN CLI command status scripts or REST GET/POST requests verifying target Gateway IPs.
  * Submit API calls to add AD user accounts to security groups that automatically permit remote gateway VPN client access.
