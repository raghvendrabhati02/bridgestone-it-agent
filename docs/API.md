# API Reference – Bridgestone IT Agent

> **Base URL (development):** `http://localhost:8000`  
> **Base URL (production):** `https://<your-domain>/api`  
> **OpenAPI UI:** `http://localhost:8000/docs`  
> **Version:** 1.0.0

All protected endpoints require a valid JWT access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

---

## Authentication (`/auth`)

### POST `/auth/login`
Authenticate a user and receive access + refresh tokens.

**Request body:**
```json
{
  "username": "employee",
  "password": "employeepassword"
}
```

**Response `200`:**
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "employee",
    "email": "employee@bridgestone.com",
    "role": "EMPLOYEE"
  }
}
```

**Error responses:** `401` – wrong credentials · `400` – account deactivated

---

### POST `/auth/refresh`
Exchange a refresh token for a new access token.

**Request body:**
```json
{ "refresh_token": "<jwt>" }
```

**Response `200`:**
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

---

### POST `/auth/logout`
Log out the current user (records a LOGOUT security event).  
Requires: `Authorization: Bearer <token>`

**Response `200`:**
```json
{ "message": "Logged out successfully" }
```

---

### GET `/auth/me`
Return the currently authenticated user's profile.  
Requires: `Authorization: Bearer <token>`

**Response `200`:**
```json
{
  "id": 1,
  "username": "employee",
  "email": "employee@bridgestone.com",
  "role": "EMPLOYEE",
  "is_active": true,
  "created_at": "2026-01-01T00:00:00"
}
```

---

## Chat & AI (`/chat`)

### POST `/chat`
Send a message to the IT support AI. The backend routes the message through `IntentRouter → ConversationService → KnowledgeEngine → GeminiService`.

**Requires:** `Authorization: Bearer <token>`

**Request body:**
```json
{
  "message": "My VPN is not working",
  "session_id": "optional-existing-session-id"
}
```

**Response `200`:**
```json
{
  "session_id": "uuid",
  "category": "VPN",
  "action": "TROUBLESHOOTING_STEP",
  "response": "Let me help you troubleshoot your VPN. First, please check...",
  "history_length": 1,
  "ticket_created": false,
  "ticket_id": null,
  "servicenow_id": null,
  "assigned_team": null,
  "priority": null,
  "sla_hours": null,
  "notifications_created": false,
  "ticket": null,
  "request_type": null,
  "approval_status": null,
  "requires_approval": false,
  "ticket_status": "UNDERSTANDING",
  "tool_result": { "tool_name": "vpn_tools", "status": "SUCCESS", "data": {} },
  "approval_required": false,
  "recommended_action": null,
  "action_result": null,
  "source": "VPN Troubleshooting Guide",
  "context_used": true
}
```

**Action values:**

| Action | Meaning |
|--------|---------|
| `TROUBLESHOOTING_STEP` | Active troubleshooting step delivered |
| `TICKET_CREATED` | Ticket was created in ServiceNow |
| `WAIT_FOR_APPROVAL` | VPN restoration request awaiting manager approval |
| `ACCESS_DENIED` | RBAC blocked the action (Employee attempting privileged action) |
| `ASK_MORE_INFO` | Gathering more information |
| `RESTART` | Session restarted |
| `CANCEL` | Session cancelled |

---

## Tickets (`/tickets`)

### GET `/tickets`
Get all tickets. Response is filtered by role: Employees see only their own tickets.  
**Requires:** Auth

**Query params:** `status`, `category`, `priority`, `created_by`, `request_type`

**Response `200`:**
```json
{
  "count": 5,
  "tickets": [
    {
      "ticket_id": "TKT-001",
      "category": "VPN",
      "description": "VPN not connecting",
      "assigned_team": "IT Support",
      "priority": "HIGH",
      "sla_hours": 4,
      "status": "IN_PROGRESS",
      "servicenow_id": "INC0000001",
      "created_by": "employee",
      "created_at": "2026-07-11T10:00:00Z",
      "updated_at": "2026-07-11T10:30:00Z",
      "request_type": "INCIDENT",
      "approval_status": "NOT_REQUIRED",
      "sla_state": "HEALTHY",
      "sla_breached": false
    }
  ]
}
```

---

### POST `/ticket`
Create a support ticket directly (admin use).  
**Requires:** Auth

**Request body:**
```json
{
  "message": "VPN not working after password change",
  "session_id": "optional-session-id",
  "username": "employee"
}
```

---

### POST `/tickets/{ticket_id}/action`
Perform a lifecycle action on a ticket.  
**Requires:** Auth (MANAGER or ADMIN for most transitions)

**Request body:**
```json
{
  "action": "approve",
  "comment": "Approved for hardware allocation"
}
```

**Supported actions:** `approve` · `reject` · `assign` · `start` · `resolve` · `close`

---

### GET `/tickets/{ticket_id}/details`
Get full ticket details including all metadata and SLA status.  
**Requires:** Auth

---

### GET `/tickets/{ticket_id}/timeline`
Get the full event timeline for a ticket.  
**Requires:** Auth

---

### GET `/tickets/{ticket_id}/comments`
List all comments on a ticket.  
**Requires:** Auth

---

### POST `/tickets/{ticket_id}/comments`
Add a comment to a ticket.  
**Requires:** Auth

**Request body:**
```json
{ "content": "Engineer has been assigned and is investigating." }
```

---

### POST `/tickets/{ticket_id}/assign`
Assign a ticket to an engineer.  
**Requires:** Auth (MANAGER or ADMIN)

**Request body:**
```json
{ "engineer": "john.doe", "comment": "Assigned to network team" }
```

---

### POST `/tickets/{ticket_id}/reopen`
Reopen a resolved or closed ticket.  
**Requires:** Auth

**Request body:**
```json
{ "reason": "Issue recurred after resolution" }
```

---

### POST `/tickets/{ticket_id}/csat`
Submit a customer satisfaction score for a resolved ticket.  
**Requires:** Auth (ticket creator only)

**Request body:**
```json
{ "score": 5, "feedback": "Very helpful!" }
```

---

### GET `/tickets/check-duplicate`
Check for potential duplicate tickets before creating one.  
**Requires:** Auth

**Query params:** `category`, `description`

---

## Service Catalog & Requests (`/service-catalog`, `/service-requests`)

### GET `/service-catalog`
List all available service catalog items.  
**Requires:** Auth

---

### GET `/service-requests`
List service requests. Filtered by role.  
**Requires:** Auth

---

### POST `/service-requests`
Submit a service request from the catalog.  
**Requires:** Auth

---

### POST `/service-requests/{request_id}/action`
Approve or reject a service request.  
**Requires:** Auth (MANAGER or ADMIN)

---

## ITSM Workflow (`/api/itsm`)

### GET `/api/itsm/manager-approvals`
Returns all `SERVICE_REQUEST` and `PRIVILEGED_ACTION` tickets with `approval_status=PENDING`.  
**Requires:** Auth (MANAGER or ADMIN)

**Response `200`:**
```json
{
  "count": 2,
  "tickets": [
    {
      "ticket_id": "TKT-005",
      "category": "SOFTWARE_INSTALLATION",
      "description": "Install Zoom for project meetings",
      "priority": "MEDIUM",
      "status": "WAITING_MANAGER",
      "created_by": "employee",
      "request_type": "SERVICE_REQUEST",
      "approval_status": "PENDING",
      "manager": null,
      "sla_state": "HEALTHY"
    }
  ]
}
```

---

### GET `/api/itsm/admin-queue`
Returns all tickets visible to administrators (full ITSM queue).  
**Requires:** Auth (ADMIN)

---

### GET `/api/itsm/my-requests`
Returns the current user's service requests.  
**Requires:** Auth

---

### GET `/api/itsm/manager-tickets`
Returns tickets assigned to or manageable by the current manager.  
**Requires:** Auth (MANAGER or ADMIN)

---

## Notifications (`/notifications`)

### GET `/notifications`
Get notifications for the current user.  
**Requires:** Auth

---

## SLA (`/sla`)

### GET `/sla`
Get SLA status for all tickets.  
**Requires:** Auth

### GET `/sla/dashboard-metrics`
Get aggregate SLA metrics for the dashboard.  
**Requires:** Auth

### GET `/sla/escalations`
Get all tickets currently in escalated SLA states.  
**Requires:** Auth

### GET `/sla/ticket/{ticket_id}`
Get detailed SLA information for a specific ticket.  
**Requires:** Auth

---

## Knowledge Base Admin (`/api/admin/knowledge`)

### GET `/api/admin/knowledge/articles`
List all knowledge base articles.  
**Requires:** Auth (ADMIN)

### GET `/api/admin/knowledge/articles/{article_id}`
Get a single article by ID.  
**Requires:** Auth (ADMIN)

### POST `/api/admin/knowledge/articles`
Create a new knowledge base article.  
**Requires:** Auth (ADMIN)

### POST `/api/admin/knowledge/articles/{article_id}/publish`
Publish a draft article.  
**Requires:** Auth (ADMIN)

### POST `/api/admin/knowledge/articles/{article_id}/archive`
Archive an active article.  
**Requires:** Auth (ADMIN)

### POST `/api/admin/knowledge/articles/{article_id}/upload`
Upload a file (image/PDF) to attach to an article.  
**Requires:** Auth (ADMIN)

### GET `/api/admin/knowledge/articles/{article_id}/versions`
Get version history of an article.  
**Requires:** Auth (ADMIN)

---

## Scheduler / Jobs (`/jobs`)

### GET `/jobs`
List all scheduled jobs and their statuses.  
**Requires:** Auth (ADMIN)

### GET `/jobs/history`
Get execution history for all jobs.  
**Requires:** Auth (ADMIN)

### POST `/jobs/run/{job_name}`
Trigger a scheduled job manually.  
**Requires:** Auth (ADMIN)

### POST `/jobs/enable/{job_name}`
Enable a disabled scheduled job.  
**Requires:** Auth (ADMIN)

### POST `/jobs/disable/{job_name}`
Disable an active scheduled job.  
**Requires:** Auth (ADMIN)

---

## Audit & Security Logs

### GET `/audit-logs`
Get all audit log entries.  
**Requires:** Auth (ADMIN)

### GET `/approvals`
Get all approval history records.  
**Requires:** Auth (ADMIN)

### GET `/agent-traces`
Get agent reasoning traces for all sessions.  
**Requires:** Auth (ADMIN)

### GET `/rbac-audit-logs`
Get RBAC access denial audit logs.  
**Requires:** Auth (ADMIN)

### GET `/admin/security-logs`
Get security event logs (logins, failures, permission denials).  
**Requires:** Auth (ADMIN)

---

## Observability

### GET `/health`
Simple health check.

**Response `200`:**
```json
{ "status": "healthy" }
```

---

### GET `/system-status`
Deep system status check including DB, Gemini, adapters, and scheduler.  
**Requires:** Auth

**Response `200`:**
```json
{
  "status": "healthy",
  "database": "healthy",
  "gemini": "healthy",
  "adapters": {
    "ServiceNow": { "status": "healthy", "latency": 0.0, "details": "Mock Mode active." },
    "Microsoft Graph": { "status": "healthy", "latency": 0.0, "details": "Mock Mode active." },
    "Active Directory": { "status": "healthy", "latency": 0.0, "details": "Mock Mode active." },
    "VPN": "healthy"
  },
  "scheduler": {
    "running": true,
    "jobs": [...]
  }
}
```

---

### GET `/metrics`
Prometheus metrics endpoint.  
**Content-Type:** `text/plain; version=0.0.4`

---

## ServiceNow Integration (`/servicenow`)

### GET `/servicenow/incidents`
List all ServiceNow incidents.  
**Requires:** Auth

### GET `/servicenow/incidents/{id}`
Get a specific ServiceNow incident by ID.  
**Requires:** Auth

### POST `/servicenow/incidents`
Create a new ServiceNow incident.  
**Requires:** Auth

### GET `/servicenow/requests`
List all ServiceNow requests.  
**Requires:** Auth

---

## Microsoft Graph / Entra ID

### GET `/microsoftgraph/users`
List all users from Microsoft Graph.  
**Requires:** Auth (ADMIN)

### GET `/microsoftgraph/groups`
List all groups from Microsoft Graph.  
**Requires:** Auth (ADMIN)

### GET `/entra/users`
List Entra ID users.  
**Requires:** Auth (ADMIN)

### GET `/entra/groups`
List Entra ID groups.  
**Requires:** Auth (ADMIN)

### GET `/entra/stats`
Get Entra ID statistics.  
**Requires:** Auth (ADMIN)

---

## IT Actions & Device Agent

### GET `/actions`
List all recorded IT action executions.  
**Requires:** Auth

### POST `/api/it-actions/execute`
Execute an IT action.  
**Requires:** Auth (ADMIN)

### POST `/api/device-agent/action`
Send a command to the device agent.  
**Requires:** Auth (ADMIN)

---

## Common Error Responses

| Status | Meaning |
|--------|---------|
| `400` | Bad request (missing or invalid fields) |
| `401` | Authentication token missing or expired |
| `403` | Insufficient permissions (role check failed) |
| `404` | Resource not found |
| `500` | Internal server error |
| `503` | Database locked or temporarily unavailable |
| `504` | Request timed out |

All errors return:
```json
{
  "detail": "Human-readable error message",
  "error_code": "ExceptionClassName"
}
```
