# API Reference

> **Project:** Bridgestone IT AI Assistant · **Last updated:** 2026-07-26  
> **Base URL (development):** `http://localhost:8000`  
> **Interactive Swagger UI:** `http://localhost:8000/docs`  
> **ReDoc UI:** `http://localhost:8000/redoc`

All protected endpoints require a valid JWT bearer access token passed in the HTTP `Authorization` header:
```http
Authorization: Bearer <access_token>
```

---

## Table of Contents

1. [Authentication (`/auth`)](#1-authentication-auth)
2. [AI Support Chat & Copilot (`/chat`, `/system`)](#2-ai-support-chat--copilot-chatsystem)
3. [Tickets & Service Requests (`/tickets`, `/service-requests`, `/service-catalog`)](#3-tickets--service-requests-ticketsservice-requestsservice-catalog)
4. [Ticket Comments (`/tickets/{ticket_id}/comments`, `/comments`)](#4-ticket-comments-ticketsticket_idcommentscomments)
5. [Manager & Admin ITSM Workflows (`/api/itsm`)](#5-manager--admin-itsm-workflows-apiitsm)
6. [SLA Monitoring Engine (`/sla`)](#6-sla-monitoring-engine-sla)
7. [Analytics & Executive Dashboard (`/api/analytics`, `/admin/dashboard`)](#7-analytics--executive-dashboard-apianalyticsadmindashboard)
8. [Knowledge Base Administration (`/api/admin/knowledge/articles`)](#8-knowledge-base-administration-apiadminknowledgearticles)
9. [Audit, Security & RBAC Logs (`/actions`, `/audit-logs`, `/approvals`, `/agent-traces`, `/admin/security-logs`, `/rbac-audit-logs`, `/notifications`)](#9-audit-security--rbac-logs-actionsaudit-logsapprovalsagent-tracesadminsecurity-logsrbac-audit-logsnotifications)
10. [Enterprise Integration Adapters (`/servicenow`, `/microsoftgraph`, `/entra`)](#10-enterprise-integration-adapters-servicenowmicrosoftgraphentra)
11. [Background Job Management (`/jobs`)](#11-background-job-management-jobs)
12. [System Health & Observability (`/`, `/health`, `/ready`, `/metrics`, `/system-status`, `/health/servicenow`, `/metadata/health`)](#12-system-health--observability-healthreadymetricssystem-statushealthservicenowmetadatahealth)

---

## 1. Authentication (`/auth`)

### POST `/auth/login`
- **Endpoint:** `/auth/login`
- **HTTP Method:** `POST`
- **Description:** Authenticates user credentials against the database, checks active status, enforces rate limiting, logs security events (`LOGIN` or `FAILED_LOGIN`), and returns JWT access and refresh tokens.
- **Authentication Required:** No
- **User Roles:** Public
- **Request Body:**
  ```json
  {
    "username": "employee",
    "password": "employeepassword"
  }
  ```
- **Response Body:**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "refresh_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "username": "employee",
      "email": "employee@bridgestone.com",
      "role": "EMPLOYEE"
    }
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: User account is deactivated.
  - `401 Unauthorized`: Incorrect username or password.
  - `429 Too Many Requests`: Login rate limit exceeded (10 requests / 60 seconds).
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"employee","password":"employeepassword"}'
  ```
- **Example Response:**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "refresh_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer",
    "user": { "id": 1, "username": "employee", "email": "employee@bridgestone.com", "role": "EMPLOYEE" }
  }
  ```
- **Related Services:** `app/api/auth.py`, `app/core/security.py`, `app/services/security_service.py`

---

### POST `/auth/refresh`
- **Endpoint:** `/auth/refresh`
- **HTTP Method:** `POST`
- **Description:** Validates a refresh token and generates a new short-lived access token.
- **Authentication Required:** No
- **User Roles:** Public
- **Request Body:**
  ```json
  {
    "refresh_token": "eyJhbGciOiJIUzI1Ni..."
  }
  ```
- **Response Body:**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer"
  }
  ```
- **Error Responses:**
  - `401 Unauthorized`: Refresh token expired or invalid.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/auth/refresh \
    -H "Content-Type: application/json" \
    -d '{"refresh_token":"eyJhbGciOiJIUzI1..."}'
  ```
- **Example Response:**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer"
  }
  ```
- **Related Services:** `app/api/auth.py`, `app/core/security.py`

---

### POST `/auth/logout`
- **Endpoint:** `/auth/logout`
- **HTTP Method:** `POST`
- **Description:** Logs out the currently authenticated user and records a `LOGOUT` audit event in the database.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "message": "Logged out successfully"
  }
  ```
- **Error Responses:**
  - `401 Unauthorized`: Missing or invalid JWT access token.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/auth/logout \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "message": "Logged out successfully" }
  ```
- **Related Services:** `app/api/auth.py`, `app/services/security_service.py`

---

### GET `/auth/me`
- **Endpoint:** `/auth/me`
- **HTTP Method:** `GET`
- **Description:** Returns profile and role details for the currently authenticated user.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "id": 1,
    "username": "employee",
    "email": "employee@bridgestone.com",
    "role": "EMPLOYEE",
    "is_active": true,
    "created_at": "2026-01-01T00:00:00Z"
  }
  ```
- **Error Responses:**
  - `401 Unauthorized`: Token expired or invalid.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/auth/me \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "id": 1, "username": "employee", "email": "employee@bridgestone.com", "role": "EMPLOYEE", "is_active": true, "created_at": "2026-01-01T00:00:00Z" }
  ```
- **Related Services:** `app/api/auth.py`, `app/core/security.py`

---

## 2. AI Support Chat & Copilot (`/chat`, `/system`)

### POST `/chat`
- **Endpoint:** `/chat`
- **HTTP Method:** `POST`
- **Description:** Primary entry point for AI support interactions. Processes user messages through PromptGuard, state machine, and the 18-node LangGraph troubleshooting pipeline.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:**
  ```json
  {
    "message": "My VPN is not connecting",
    "session_id": "sess-12345"
  }
  ```
- **Response Body:**
  ```json
  {
    "session_id": "sess-12345",
    "category": "VPN",
    "action": "TROUBLESHOOTING_STEP",
    "response": "Let us check your network connection first. Are you connected to corporate Wi-Fi?",
    "history_length": 2,
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
    "tool_result": null,
    "approval_required": false,
    "recommended_action": null,
    "action_result": null
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: High-risk prompt injection detected or empty message.
  - `401 Unauthorized`: Unauthenticated request.
  - `429 Too Many Requests`: Rate limit exceeded (30 requests / 60 seconds).
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/chat \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"message":"VPN error","session_id":"sess-99"}'
  ```
- **Example Response:**
  ```json
  { "session_id": "sess-99", "category": "VPN", "action": "TROUBLESHOOTING_STEP", "response": "Have you tried restarting Cisco AnyConnect?" }
  ```
- **Related Services:** `app/main.py`, `app/graph/graph.py`, `app/services/conversation_service.py`, `app/services/prompt_guard.py`

---

### GET `/system/provider`
- **Endpoint:** `/system/provider`
- **HTTP Method:** `GET`
- **Description:** Returns the active LLM provider name and operational status (`GeminiProvider`, `ClaudeProvider`, or fallback).
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "provider": "GeminiProvider",
    "status": "READY"
  }
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
  - `403 Forbidden`: Insufficient role permissions.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/system/provider \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "provider": "GeminiProvider", "status": "READY" }
  ```
- **Related Services:** `app/services/ai_provider.py`

---

## 3. Tickets & Service Requests (`/tickets`, `/service-requests`, `/service-catalog`)

### GET `/tickets`
- **Endpoint:** `/tickets`
- **HTTP Method:** `GET`
- **Description:** Fetches support tickets. Employees see only their own tickets; Managers see team tickets; Admins see all tickets. Supports filtering and pagination parameters.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Query Parameters:** `status`, `priority`, `category`, `assigned_team`, `assigned_engineer`, `created_by`, `sla_state`, `sla_breached`, `search`, `created_after`, `created_before`, `updated_after`, `updated_before`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "count": 1,
    "tickets": [
      {
        "ticket_id": "INC0071800",
        "category": "VPN",
        "description": "VPN connection failure",
        "issue_description": "VPN connection failure",
        "assigned_team": "Network Team",
        "assigned_engineer": null,
        "priority": "MEDIUM",
        "status": "NEW",
        "created_by": "employee",
        "created_at": "2026-07-26T12:00:00Z",
        "updated_at": "2026-07-26T12:00:00Z",
        "resolved_at": null,
        "closed_at": null,
        "request_type": "INCIDENT",
        "manager": null,
        "approval_status": "NOT_REQUIRED",
        "assignment_group": "Network Team",
        "sla_hours": 8,
        "sla_state": "HEALTHY",
        "sla_breached": false
      }
    ]
  }
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
- **Example Request:**
  ```bash
  curl -X GET "http://localhost:8000/tickets?status=NEW" \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "count": 1, "tickets": [{ "ticket_id": "INC0071800", "status": "NEW", "category": "VPN" }] }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`, `app/database/repositories/ticket_repository.py`

---

### POST `/ticket`
- **Endpoint:** `/ticket`
- **HTTP Method:** `POST`
- **Description:** Directly creates an IT support ticket or service request in the database and ServiceNow.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:**
  ```json
  {
    "category": "Software",
    "issue_description": "Install VS Code for development work",
    "short_description": "VS Code Installation",
    "assigned_team": "IT Support"
  }
  ```
- **Response Body:**
  ```json
  {
    "ticket_id": "INC0071801",
    "category": "Software",
    "description": "Install VS Code for development work",
    "issue_description": "Install VS Code for development work",
    "assigned_team": "IT Support",
    "priority": "MEDIUM",
    "status": "WAITING_MANAGER",
    "created_by": "employee",
    "created_at": "2026-07-26T12:00:00Z",
    "request_type": "SERVICE_REQUEST",
    "manager": "manager",
    "approval_status": "PENDING",
    "requires_approval": true,
    "servicenow_id": "sys_12345"
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: Missing mandatory fields (`category` or `issue_description`).
  - `401 Unauthorized`: Token missing or invalid.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/ticket \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"category":"VPN","issue_description":"VPN fails to authenticate"}'
  ```
- **Example Response:**
  ```json
  { "ticket_id": "INC0071802", "status": "NEW", "request_type": "INCIDENT" }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`, `app/services/ticket_orchestrator.py`

---

### GET `/tickets/{ticket_id}/details`
- **Endpoint:** `/tickets/{ticket_id}/details`
- **HTTP Method:** `GET`
- **Description:** Retrieves full ticket details, including SLA deadlines, manager approval status, and temporary admin credentials if granted.
- **Authentication Required:** Yes
- **User Roles:** `EMPLOYEE` (own tickets), `MANAGER`, `ADMIN`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "ticket_id": "INC0071801",
    "category": "Software",
    "description": "Install VS Code",
    "status": "ACCESS_GRANTED",
    "request_type": "SERVICE_REQUEST",
    "approval_status": "APPROVED",
    "approved_by": "manager",
    "approved_at": "2026-07-26T12:05:00Z",
    "approval_notes": "Approved for dev project",
    "laps_active": true,
    "temp_admin_credentials": {
      "username": ".\\Administrator",
      "password": "Temp@4821#",
      "status": "ACTIVE",
      "valid_for_minutes": 15
    }
  }
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
  - `403 Forbidden`: User attempting to access another employee's ticket.
  - `404 Not Found`: Ticket ID does not exist.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/tickets/INC0071801/details \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "ticket_id": "INC0071801", "status": "ACCESS_GRANTED", "approval_status": "APPROVED" }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### GET `/tickets/{ticket_id}/timeline`
- **Endpoint:** `/tickets/{ticket_id}/timeline`
- **HTTP Method:** `GET`
- **Description:** Returns the chronological audit event timeline for a ticket (creation, state transitions, approvals, comments).
- **Authentication Required:** Yes
- **User Roles:** `EMPLOYEE` (own tickets), `MANAGER`, `ADMIN`
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "timestamp": "2026-07-26T12:00:00Z",
      "title": "Ticket Created",
      "description": "Service request submitted by employee",
      "type": "SYSTEM",
      "user": "employee",
      "role": "EMPLOYEE"
    },
    {
      "timestamp": "2026-07-26T12:05:00Z",
      "title": "Manager Approved",
      "description": "Approved by manager: Approved for dev project",
      "type": "APPROVAL",
      "user": "manager",
      "role": "MANAGER"
    }
  ]
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/tickets/INC0071801/timeline \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "timestamp": "2026-07-26T12:00:00Z", "title": "Ticket Created" } ]
  ```
- **Related Services:** `app/main.py`, `app/services/timeline_service.py`

---

### POST `/tickets/{ticket_id}/action`
- **Endpoint:** `/tickets/{ticket_id}/action`
- **HTTP Method:** `POST`
- **Description:** Executes state transition actions on a ticket (`APPROVE`, `REJECT`, `ASSIGN`, `RESOLVE`, `CLOSE`).
- **Authentication Required:** Yes
- **User Roles:** `MANAGER` (approvals), `ADMIN` (all actions)
- **Request Body:**
  ```json
  {
    "action": "APPROVE",
    "notes": "Approved by manager"
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071801",
    "new_status": "READY_FOR_ADMIN",
    "action": "APPROVE"
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: RBAC check failed (e.g. EMPLOYEE attempting APPROVE action).
  - `404 Not Found`: Ticket ID not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/tickets/INC0071801/action \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"action":"APPROVE","notes":"Looks good"}'
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071801", "new_status": "READY_FOR_ADMIN" }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`, `app/services/workflow_service.py`

---

### POST `/tickets/{ticket_id}/assign`
- **Endpoint:** `/tickets/{ticket_id}/assign`
- **HTTP Method:** `POST`
- **Description:** Reassigns a ticket to a specific assignment group or engineer.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:**
  ```json
  {
    "assigned_team": "Infrastructure",
    "assigned_engineer": "john.admin"
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071800",
    "assigned_team": "Infrastructure",
    "assigned_engineer": "john.admin"
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Insufficient role.
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/tickets/INC0071800/assign \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"assigned_team":"Infrastructure","assigned_engineer":"john.admin"}'
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071800", "assigned_team": "Infrastructure" }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### GET `/tickets/{ticket_id}/assignment-history`
- **Endpoint:** `/tickets/{ticket_id}/assignment-history`
- **HTTP Method:** `GET`
- **Description:** Returns past assignment changes for a ticket.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "assigned_team": "Network Team",
      "assigned_engineer": "admin",
      "changed_by": "admin",
      "timestamp": "2026-07-26T12:10:00Z"
    }
  ]
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/tickets/INC0071800/assignment-history \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "assigned_team": "Network Team", "changed_by": "admin" } ]
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### POST `/tickets/{ticket_id}/reopen`
- **Endpoint:** `/tickets/{ticket_id}/reopen`
- **HTTP Method:** `POST`
- **Description:** Reopens a resolved or closed ticket with a stated reason.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:**
  ```json
  {
    "reason": "Issue persisted after restart"
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071800",
    "status": "REOPENED",
    "reason": "Issue persisted after restart"
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: Missing reason string.
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/tickets/INC0071800/reopen \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"reason":"Issue recurred"}'
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071800", "status": "REOPENED" }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### POST `/tickets/{ticket_id}/csat`
- **Endpoint:** `/tickets/{ticket_id}/csat`
- **HTTP Method:** `POST`
- **Description:** Submits customer satisfaction (CSAT) rating and feedback for a resolved ticket.
- **Authentication Required:** Yes
- **User Roles:** `EMPLOYEE`
- **Request Body:**
  ```json
  {
    "rating": 5,
    "feedback": "Great and fast help!"
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071800",
    "rating": 5
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: Rating out of bounds (1 to 5).
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/tickets/INC0071800/csat \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"rating":5,"feedback":"Excellent"}'
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071800", "rating": 5 }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### GET `/tickets/{ticket_id}/ai-diagnosis`
- **Endpoint:** `/tickets/{ticket_id}/ai-diagnosis` (alias `/api/tickets/{ticket_id}/ai-diagnosis`)
- **HTTP Method:** `GET`
- **Description:** Returns AI-assisted diagnostic root cause summary for a specific ticket.
- **Authentication Required:** Yes
- **User Roles:** `MANAGER`, `ADMIN`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "ticket_id": "INC0071800",
    "diagnosis": "VPN authentication timeout caused by expired Active Directory password.",
    "confidence": 0.92,
    "recommended_fix": "Prompt user for AD password renewal via self-service portal."
  }
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
  - `404 Not Found`: Ticket ID not found.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/tickets/INC0071800/ai-diagnosis \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "ticket_id": "INC0071800", "confidence": 0.92, "diagnosis": "VPN timeout..." }
  ```
- **Related Services:** `app/main.py`, `app/services/reasoning_service.py`

---

### GET `/tickets/check-duplicate`
- **Endpoint:** `/tickets/check-duplicate`
- **HTTP Method:** `GET`
- **Description:** Evaluates description text against open tickets to detect potential duplicates using semantic similarity checks.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Query Parameters:** `description` (required)
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "has_duplicate": true,
    "similar_tickets": [
      {
        "ticket_id": "INC0071799",
        "category": "VPN",
        "description": "VPN connection failure from home",
        "similarity_score": 0.89
      }
    ]
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: Missing `description` query parameter.
- **Example Request:**
  ```bash
  curl -X GET "http://localhost:8000/tickets/check-duplicate?description=VPN%20connection%20issue" \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "has_duplicate": true, "similar_tickets": [{ "ticket_id": "INC0071799", "similarity_score": 0.89 }] }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### POST `/tickets/confirm-duplicate`
- **Endpoint:** `/tickets/confirm-duplicate`
- **HTTP Method:** `POST`
- **Description:** Links a ticket to a parent master ticket as a confirmed duplicate.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:**
  ```json
  {
    "ticket_id": "INC0071800",
    "parent_id": "INC0071799"
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071800",
    "parent_id": "INC0071799",
    "status": "DUPLICATE"
  }
  ```
- **Error Responses:**
  - `404 Not Found`: Ticket or parent ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/tickets/confirm-duplicate \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"ticket_id":"INC0071800","parent_id":"INC0071799"}'
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071800", "parent_id": "INC0071799" }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### POST `/tickets/dismiss-duplicate`
- **Endpoint:** `/tickets/dismiss-duplicate`
- **HTTP Method:** `POST`
- **Description:** Dismisses a duplicate warning for a ticket.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:**
  ```json
  {
    "ticket_id": "INC0071800"
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071800",
    "dismissed": true
  }
  ```
- **Error Responses:**
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/tickets/dismiss-duplicate \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"ticket_id":"INC0071800"}'
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071800", "dismissed": true }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### GET `/service-catalog`
- **Endpoint:** `/service-catalog`
- **HTTP Method:** `GET`
- **Description:** Returns the IT Service Catalog list of available software and hardware request templates.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "id": "sc-vscode",
      "name": "Visual Studio Code",
      "category": "Software",
      "requires_approval": true,
      "description": "Code editor for development"
    }
  ]
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/service-catalog \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "id": "sc-vscode", "name": "Visual Studio Code", "requires_approval": true } ]
  ```
- **Related Services:** `app/main.py`

---

### POST `/service-requests`
- **Endpoint:** `/service-requests`
- **HTTP Method:** `POST`
- **Description:** Submits a Service Catalog item request.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:**
  ```json
  {
    "catalog_item_id": "sc-vscode",
    "justification": "Required for development task"
  }
  ```
- **Response Body:**
  ```json
  {
    "request_id": "SR00102",
    "status": "WAITING_MANAGER",
    "requires_approval": true
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: Missing item ID or justification.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/service-requests \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"catalog_item_id":"sc-vscode","justification":"Dev work"}'
  ```
- **Example Response:**
  ```json
  { "request_id": "SR00102", "status": "WAITING_MANAGER" }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### GET `/service-requests`
- **Endpoint:** `/service-requests`
- **HTTP Method:** `GET`
- **Description:** Lists service requests filtered by current user role.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "request_id": "SR00102",
      "item": "Visual Studio Code",
      "status": "WAITING_MANAGER"
    }
  ]
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/service-requests \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "request_id": "SR00102", "status": "WAITING_MANAGER" } ]
  ```
- **Related Services:** `app/main.py`

---

### GET `/service-requests/{request_id}/details`
- **Endpoint:** `/service-requests/{request_id}/details`
- **HTTP Method:** `GET`
- **Description:** Details for a specific service request.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "request_id": "SR00102",
    "item": "Visual Studio Code",
    "status": "WAITING_MANAGER",
    "manager": "manager"
  }
  ```
- **Error Responses:**
  - `404 Not Found`: Request not found.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/service-requests/SR00102/details \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "request_id": "SR00102", "status": "WAITING_MANAGER" }
  ```
- **Related Services:** `app/main.py`

---

### POST `/service-requests/{request_id}/action`
- **Endpoint:** `/service-requests/{request_id}/action`
- **HTTP Method:** `POST`
- **Description:** Executes an action on a service request.
- **Authentication Required:** Yes
- **User Roles:** `MANAGER`, `ADMIN`
- **Request Body:**
  ```json
  {
    "action": "APPROVE",
    "notes": "Approved for dev work"
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "request_id": "SR00102",
    "status": "READY_FOR_ADMIN"
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Insufficient role.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/service-requests/SR00102/action \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"action":"APPROVE"}'
  ```
- **Example Response:**
  ```json
  { "success": true, "request_id": "SR00102", "status": "READY_FOR_ADMIN" }
  ```
- **Related Services:** `app/main.py`

---

## 4. Ticket Comments (`/tickets/{ticket_id}/comments`, `/comments`)

### POST `/tickets/{ticket_id}/comments`
- **Endpoint:** `/tickets/{ticket_id}/comments`
- **HTTP Method:** `POST`
- **Description:** Adds a public or internal work note comment to a ticket.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:**
  ```json
  {
    "text": "Tested remote access after router reboot. Working now.",
    "is_internal": false
  }
  ```
- **Response Body:**
  ```json
  {
    "id": 42,
    "ticket_id": "INC0071800",
    "author": "employee",
    "text": "Tested remote access after router reboot. Working now.",
    "is_internal": false,
    "created_at": "2026-07-26T12:15:00Z"
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: Empty comment text.
  - `403 Forbidden`: Employee attempting to set `is_internal=True`.
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/tickets/INC0071800/comments \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"text":"Issue resolved.","is_internal":false}'
  ```
- **Example Response:**
  ```json
  { "id": 42, "ticket_id": "INC0071800", "author": "employee", "text": "Issue resolved." }
  ```
- **Related Services:** `app/main.py`, `app/database/repositories/ticket_repository.py`

---

### GET `/tickets/{ticket_id}/comments`
- **Endpoint:** `/tickets/{ticket_id}/comments`
- **HTTP Method:** `GET`
- **Description:** Lists comments for a ticket. Non-admin/manager users will have internal notes filtered out.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "id": 42,
      "author": "employee",
      "text": "Issue resolved.",
      "is_internal": false,
      "created_at": "2026-07-26T12:15:00Z"
    }
  ]
  ```
- **Error Responses:**
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/tickets/INC0071800/comments \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "id": 42, "author": "employee", "text": "Issue resolved." } ]
  ```
- **Related Services:** `app/main.py`

---

### PUT `/comments/{comment_id}`
- **Endpoint:** `/comments/{comment_id}`
- **HTTP Method:** `PUT`
- **Description:** Edits an existing comment text. Only comment author or admin can modify.
- **Authentication Required:** Yes
- **User Roles:** Comment author or `ADMIN`
- **Request Body:**
  ```json
  {
    "text": "Updated comment text."
  }
  ```
- **Response Body:**
  ```json
  {
    "id": 42,
    "text": "Updated comment text.",
    "updated_at": "2026-07-26T12:20:00Z"
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Not comment author or admin.
  - `404 Not Found`: Comment ID not found.
- **Example Request:**
  ```bash
  curl -X PUT http://localhost:8000/comments/42 \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"text":"Updated text"}'
  ```
- **Example Response:**
  ```json
  { "id": 42, "text": "Updated text" }
  ```
- **Related Services:** `app/main.py`

---

## 5. Manager & Admin ITSM Workflows (`/api/itsm`)

### GET `/api/itsm/manager-tickets`
- **Endpoint:** `/api/itsm/manager-tickets`
- **HTTP Method:** `GET`
- **Description:** Returns all tickets assigned to or requiring approval by the authenticated manager, with optional `approval_status` filter (`PENDING`, `APPROVED`, `REJECTED`).
- **Authentication Required:** Yes
- **User Roles:** `MANAGER`, `ADMIN`
- **Query Parameters:** `approval_status` (optional)
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "count": 1,
    "tickets": [
      {
        "ticket_id": "INC0071801",
        "category": "Software",
        "description": "Install VS Code",
        "status": "WAITING_MANAGER",
        "request_type": "SERVICE_REQUEST",
        "approval_status": "PENDING",
        "created_by": "employee",
        "ai_recommendation": "Approve license assignment for Microsoft Visio."
      }
    ]
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Employee attempting manager route.
- **Example Request:**
  ```bash
  curl -X GET "http://localhost:8000/api/itsm/manager-tickets?approval_status=PENDING" \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "count": 1, "tickets": [{ "ticket_id": "INC0071801", "approval_status": "PENDING" }] }
  ```
- **Related Services:** `app/main.py`

---

### GET `/api/itsm/manager-approvals`
- **Endpoint:** `/api/itsm/manager-approvals`
- **HTTP Method:** `GET`
- **Description:** Returns all `SERVICE_REQUEST` and `PRIVILEGED_ACTION` tickets with `approval_status=PENDING`.
- **Authentication Required:** Yes
- **User Roles:** `MANAGER`, `ADMIN`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "count": 1,
    "tickets": [
      {
        "ticket_id": "INC0071801",
        "category": "Software",
        "request_type": "SERVICE_REQUEST",
        "status": "WAITING_MANAGER",
        "approval_status": "PENDING"
      }
    ]
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Employee blocked.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/api/itsm/manager-approvals \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "count": 1, "tickets": [{ "ticket_id": "INC0071801" }] }
  ```
- **Related Services:** `app/main.py`

---

### POST `/api/itsm/manager-tickets/{ticket_id}/approve`
- **Endpoint:** `/api/itsm/manager-tickets/{ticket_id}/approve`
- **HTTP Method:** `POST`
- **Description:** Approves a pending service request or privileged action, recording manager name, approval notes, and timestamp, and transitioning ticket status to `READY_FOR_ADMIN`.
- **Authentication Required:** Yes
- **User Roles:** `MANAGER`, `ADMIN`
- **Request Body:**
  ```json
  {
    "approval_notes": "Approved for dev team project."
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071801",
    "new_status": "READY_FOR_ADMIN",
    "approved_by": "manager",
    "approved_at": "2026-07-26T12:05:00Z"
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Non-manager/admin attempt.
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/api/itsm/manager-tickets/INC0071801/approve \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"approval_notes":"Approved"}'
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071801", "new_status": "READY_FOR_ADMIN" }
  ```
- **Related Services:** `app/main.py`, `app/services/ticket_service.py`

---

### POST `/api/itsm/manager-tickets/{ticket_id}/reject`
- **Endpoint:** `/api/itsm/manager-tickets/{ticket_id}/reject`
- **HTTP Method:** `POST`
- **Description:** Rejects a pending request with rejection notes and updates status to `REJECTED`.
- **Authentication Required:** Yes
- **User Roles:** `MANAGER`, `ADMIN`
- **Request Body:**
  ```json
  {
    "rejection_notes": "Software not approved for current role."
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071801",
    "new_status": "REJECTED",
    "rejected_by": "manager"
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Employee attempt.
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/api/itsm/manager-tickets/INC0071801/reject \
    -H "Authorization: Bearer <access_token>" \
    -H "Content-Type: application/json" \
    -d '{"rejection_notes":"Not needed"}'
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071801", "new_status": "REJECTED" }
  ```
- **Related Services:** `app/main.py`

---

### GET `/api/itsm/admin-queue`
- **Endpoint:** `/api/itsm/admin-queue`
- **HTTP Method:** `GET`
- **Description:** Returns all open tickets in the IT Admin Queue across the enterprise.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`
- **Query Parameters:** `status` (optional), `request_type` (optional)
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "count": 2,
    "tickets": [
      {
        "ticket_id": "INC0071801",
        "status": "READY_FOR_ADMIN",
        "approval_status": "APPROVED",
        "category": "Software"
      }
    ]
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Non-admin user.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/api/itsm/admin-queue \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "count": 2, "tickets": [{ "ticket_id": "INC0071801", "status": "READY_FOR_ADMIN" }] }
  ```
- **Related Services:** `app/main.py`

---

### POST `/api/itsm/admin-queue/{ticket_id}/grant-admin-access`
- **Endpoint:** `/api/itsm/admin-queue/{ticket_id}/grant-admin-access`
- **HTTP Method:** `POST`
- **Description:** Fulfills an approved privileged software request by issuing temporary administrator credentials (mock Windows LAPS/CyberArk integration) with a 15-minute countdown and updating ticket status to `ACCESS_GRANTED`.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071801",
    "new_status": "ACCESS_GRANTED",
    "credentials": {
      "username": ".\\Administrator",
      "password": "Temp@4821#",
      "valid_for_minutes": 15
    }
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Non-admin user attempt.
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/api/itsm/admin-queue/INC0071801/grant-admin-access \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071801", "new_status": "ACCESS_GRANTED" }
  ```
- **Related Services:** `app/main.py`, `app/database/repositories/ticket_repository.py`

---

### POST `/api/itsm/admin-queue/{ticket_id}/complete-installation`
- **Endpoint:** `/api/itsm/admin-queue/{ticket_id}/complete-installation`
- **HTTP Method:** `POST`
- **Description:** Marks a privileged request as fully completed after software installation is verified, updating status to `COMPLETED`.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "success": true,
    "ticket_id": "INC0071801",
    "new_status": "COMPLETED"
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Non-admin user.
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X POST http://localhost:8000/api/itsm/admin-queue/INC0071801/complete-installation \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "success": true, "ticket_id": "INC0071801", "new_status": "COMPLETED" }
  ```
- **Related Services:** `app/main.py`

---

### GET `/api/itsm/my-requests`
- **Endpoint:** `/api/itsm/my-requests`
- **HTTP Method:** `GET`
- **Description:** Returns the list of tickets and service requests created by the currently authenticated user.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "ticket_id": "INC0071801",
      "category": "Software",
      "status": "ACCESS_GRANTED",
      "created_at": "2026-07-26T12:00:00Z"
    }
  ]
  ```
- **Error Responses:**
  - `401 Unauthorized`: Token missing or expired.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/api/itsm/my-requests \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "ticket_id": "INC0071801", "status": "ACCESS_GRANTED" } ]
  ```
- **Related Services:** `app/main.py`

---

## 6. SLA Monitoring Engine (`/sla`)

### GET `/sla`
- **Endpoint:** `/sla`
- **HTTP Method:** `GET`
- **Description:** Returns real-time SLA status records for all open support tickets.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "ticket_id": "INC0071800",
      "priority": "MEDIUM",
      "sla_hours": 8,
      "sla_state": "HEALTHY",
      "sla_breached": false
    }
  ]
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/sla \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "ticket_id": "INC0071800", "sla_state": "HEALTHY" } ]
  ```
- **Related Services:** `app/main.py`, `app/services/sla_service.py`

---

### GET `/sla/dashboard-metrics`
- **Endpoint:** `/sla/dashboard-metrics`
- **HTTP Method:** `GET`
- **Description:** Returns aggregated SLA metric counters (`HEALTHY`, `WARNING_75`, `WARNING_90`, `BREACHED`) and overall compliance percentage.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "total_tickets": 100,
    "healthy": 92,
    "warning_75": 4,
    "warning_90": 2,
    "breached": 2,
    "compliance_rate_percent": 98.0
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Employee attempt.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/sla/dashboard-metrics \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "total_tickets": 100, "compliance_rate_percent": 98.0 }
  ```
- **Related Services:** `app/main.py`, `app/services/sla_service.py`

---

### GET `/sla/escalations`
- **Endpoint:** `/sla/escalations`
- **HTTP Method:** `GET`
- **Description:** Returns the history list of tickets that triggered SLA warning or breach escalations.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "id": 1,
      "ticket_id": "INC0071790",
      "escalation_level": "LEVEL_1",
      "triggered_at": "2026-07-26T10:00:00Z"
    }
  ]
  ```
- **Error Responses:**
  - `403 Forbidden`: Non-manager/admin attempt.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/sla/escalations \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "ticket_id": "INC0071790", "escalation_level": "LEVEL_1" } ]
  ```
- **Related Services:** `app/main.py`, `app/services/sla_escalation_service.py`

---

### GET `/sla/ticket/{ticket_id}`
- **Endpoint:** `/sla/ticket/{ticket_id}`
- **HTTP Method:** `GET`
- **Description:** Returns real-time SLA status and time remaining for a specific ticket.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "ticket_id": "INC0071800",
    "priority": "MEDIUM",
    "sla_hours": 8,
    "sla_state": "HEALTHY",
    "elapsed_percent": 25.0,
    "sla_breached": false
  }
  ```
- **Error Responses:**
  - `404 Not Found`: Ticket not found.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/sla/ticket/INC0071800 \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "ticket_id": "INC0071800", "sla_state": "HEALTHY", "elapsed_percent": 25.0 }
  ```
- **Related Services:** `app/main.py`, `app/services/sla_service.py`

---

## 7. Analytics & Executive Dashboard (`/api/analytics`, `/admin/dashboard`)

### GET `/api/analytics/overview`
- **Endpoint:** `/api/analytics/overview`
- **HTTP Method:** `GET`
- **Description:** Overview analytics metrics including total ticket counts by status, priority, and category.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "total_tickets": 150,
    "open_tickets": 25,
    "resolved_today": 12,
    "avg_resolution_hours": 3.4
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Employee attempt.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/api/analytics/overview \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "total_tickets": 150, "open_tickets": 25 }
  ```
- **Related Services:** `app/api/analytics.py`, `app/services/analytics_service.py`

---

### GET `/api/analytics/dashboard`
- **Endpoint:** `/api/analytics/dashboard`
- **HTTP Method:** `GET`
- **Description:** Complete dashboard dataset supporting custom date ranges, assignment group, and category filtering.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Query Parameters:** `time_filter`, `start_date`, `end_date`, `department`, `assignment_group`, `category`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "volume_by_day": [{ "date": "2026-07-26", "count": 14 }],
    "tickets_by_category": { "VPN": 45, "Software": 30 },
    "tickets_by_team": { "Network": 50, "IT Support": 60 }
  }
  ```
- **Error Responses:**
  - `403 Forbidden`: Non-admin/manager user.
- **Example Request:**
  ```bash
  curl -X GET "http://localhost:8000/api/analytics/dashboard?time_filter=month" \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  { "volume_by_day": [{ "date": "2026-07-26", "count": 14 }] }
  ```
- **Related Services:** `app/api/analytics.py`, `app/services/analytics_service.py`

---

### GET `/api/analytics/tickets`
- **Endpoint:** `/api/analytics/tickets`
- **HTTP Method:** `GET`
- **Description:** Detailed ticket resolution volume and trend analytics.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/api/analytics.py`

### GET `/api/analytics/sla`
- **Endpoint:** `/api/analytics/sla`
- **HTTP Method:** `GET`
- **Description:** Historical SLA compliance trend data.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/api/analytics.py`

### GET `/api/analytics/teams`
- **Endpoint:** `/api/analytics/teams`
- **HTTP Method:** `GET`
- **Description:** Metrics grouped by assignment team performance.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/api/analytics.py`

### GET `/api/analytics/categories`
- **Endpoint:** `/api/analytics/categories`
- **HTTP Method:** `GET`
- **Description:** Distribution of tickets across IT issue categories.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/api/analytics.py`

### GET `/api/analytics/security`
- **Endpoint:** `/api/analytics/security`
- **HTTP Method:** `GET`
- **Description:** Security event analytics (login attempts, privilege escalations, rate limits).
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/api/analytics.py`

### GET `/api/analytics/root-causes`
- **Endpoint:** `/api/analytics/root-causes`
- **HTTP Method:** `GET`
- **Description:** Breakdown of root-cause categories identified by AI troubleshooting.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/api/analytics.py`

### GET `/api/analytics/users`
- **Endpoint:** `/api/analytics/users`
- **HTTP Method:** `GET`
- **Description:** User activity and ticket submission metrics.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/api/analytics.py`

### GET `/api/analytics/service-requests`
- **Endpoint:** `/api/analytics/service-requests`
- **HTTP Method:** `GET`
- **Description:** Service request volume, approval turnarounds, and fulfilment times.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/api/analytics.py`

### GET `/api/analytics/engine-observability`
- **Endpoint:** `/api/analytics/engine-observability`
- **HTTP Method:** `GET`
- **Description:** AI Engine execution times, token usage, and LangGraph node latency stats.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/api/analytics.py`

---

### GET `/admin/dashboard/executive-metrics`
- **Endpoint:** `/admin/dashboard/executive-metrics`
- **HTTP Method:** `GET`
- **Description:** Executive-level KPI metrics (CSAT score, cost savings, AI resolution percentage).
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/admin/dashboard/clusters`
- **Endpoint:** `/admin/dashboard/clusters`
- **HTTP Method:** `GET`
- **Description:** Identifies recurring incident clusters using semantic grouping.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### PUT `/admin/dashboard/clusters/{cluster_id}/fix`
- **Endpoint:** `/admin/dashboard/clusters/{cluster_id}/fix`
- **HTTP Method:** `PUT`
- **Description:** Submits a systemic fix description for an incident cluster.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/admin/dashboard/knowledge-drafts`
- **Endpoint:** `/admin/dashboard/knowledge-drafts`
- **HTTP Method:** `GET`
- **Description:** Auto-generated Knowledge Base draft articles created from resolved ticket patterns.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

---

## 8. Knowledge Base Administration (`/api/admin/knowledge/articles`)

### GET `/api/admin/knowledge/articles`
- **Endpoint:** `/api/admin/knowledge/articles`
- **HTTP Method:** `GET`
- **Description:** Lists all Knowledge Base articles (drafts, published, archived).
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "article_id": "KB00101",
      "title": "GlobalProtect VPN Resolution Guide",
      "category": "VPN",
      "status": "PUBLISHED"
    }
  ]
  ```
- **Error Responses:**
  - `403 Forbidden`: Non-admin/manager attempt.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/api/admin/knowledge/articles \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "article_id": "KB00101", "title": "GlobalProtect VPN Resolution Guide" } ]
  ```
- **Related Services:** `app/services/knowledge_admin_service.py`

---

### GET `/api/admin/knowledge/articles/{article_id}`
- **Endpoint:** `/api/admin/knowledge/articles/{article_id}`
- **HTTP Method:** `GET`
- **Description:** Fetches full article content and metadata by ID.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/services/knowledge_admin_service.py`

### POST `/api/admin/knowledge/articles`
- **Endpoint:** `/api/admin/knowledge/articles`
- **HTTP Method:** `POST`
- **Description:** Creates a new Knowledge Base article draft.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:**
  ```json
  {
    "title": "Outlook Connectivity Fix",
    "category": "Outlook",
    "problem": "Outlook hangs on startup",
    "troubleshooting_steps": ["Start in Safe Mode", "Disable add-ins"]
  }
  ```
- **Response Body:**
  ```json
  {
    "article_id": "KB00102",
    "status": "DRAFT"
  }
  ```
- **Related Services:** `app/services/knowledge_admin_service.py`

### PUT `/api/admin/knowledge/articles/{article_id}`
- **Endpoint:** `/api/admin/knowledge/articles/{article_id}`
- **HTTP Method:** `PUT`
- **Description:** Updates an existing Knowledge Base article content.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/services/knowledge_admin_service.py`

### DELETE `/api/admin/knowledge/articles/{article_id}`
- **Endpoint:** `/api/admin/knowledge/articles/{article_id}`
- **HTTP Method:** `DELETE`
- **Description:** Deletes an article from the system.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`
- **Related Services:** `app/services/knowledge_admin_service.py`

### POST `/api/admin/knowledge/articles/{article_id}/publish`
- **Endpoint:** `/api/admin/knowledge/articles/{article_id}/publish`
- **HTTP Method:** `POST`
- **Description:** Publishes a draft KB article, making it live for AI troubleshooting retrieval.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/services/knowledge_admin_service.py`

### POST `/api/admin/knowledge/articles/{article_id}/archive`
- **Endpoint:** `/api/admin/knowledge/articles/{article_id}/archive`
- **HTTP Method:** `POST`
- **Description:** Archives a KB article so it is no longer used for active troubleshooting.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/services/knowledge_admin_service.py`

### GET `/api/admin/knowledge/articles/{article_id}/versions`
- **Endpoint:** `/api/admin/knowledge/articles/{article_id}/versions`
- **HTTP Method:** `GET`
- **Description:** Returns full version history for an article.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/services/knowledge_admin_service.py`

### GET `/api/admin/knowledge/articles/{article_id}/versions/{version}`
- **Endpoint:** `/api/admin/knowledge/articles/{article_id}/versions/{version}`
- **HTTP Method:** `GET`
- **Description:** Fetches content of a specific past version.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/services/knowledge_admin_service.py`

### POST `/api/admin/knowledge/articles/{article_id}/upload`
- **Endpoint:** `/api/admin/knowledge/articles/{article_id}/upload`
- **HTTP Method:** `POST`
- **Description:** Uploads a screenshot file attachment for a Knowledge Base article.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:** `multipart/form-data` with `file`
- **Related Services:** `app/services/knowledge_admin_service.py`

---

## 9. Audit, Security & RBAC Logs (`/actions`, `/audit-logs`, `/approvals`, `/agent-traces`, `/admin/security-logs`, `/rbac-audit-logs`, `/notifications`)

### GET `/notifications`
- **Endpoint:** `/notifications`
- **HTTP Method:** `GET`
- **Description:** Returns in-app notifications for the authenticated user (ticket status changes, SLA warnings).
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "id": 1,
      "recipient": "employee",
      "message": "Your ticket INC0071801 has been approved.",
      "created_at": "2026-07-26T12:05:00Z",
      "read": false
    }
  ]
  ```
- **Error Responses:**
  - `401 Unauthorized`: Unauthenticated.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/notifications \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "id": 1, "message": "Your ticket INC0071801 has been approved." } ]
  ```
- **Related Services:** `app/main.py`, `app/services/notification_service.py`

---

### GET `/actions`
- **Endpoint:** `/actions`
- **HTTP Method:** `GET`
- **Description:** Returns system action logs.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/audit-logs`
- **Endpoint:** `/audit-logs`
- **HTTP Method:** `GET`
- **Description:** General audit trail of user and system actions.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/approvals`
- **Endpoint:** `/approvals`
- **HTTP Method:** `GET`
- **Description:** History of manager approval decisions across all service requests.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/agent-traces`
- **Endpoint:** `/agent-traces`
- **HTTP Method:** `GET`
- **Description:** Detailed LLM reasoning trace logs per chat session.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/admin/security-logs`
- **Endpoint:** `/admin/security-logs`
- **HTTP Method:** `GET`
- **Description:** Security event log audit records (logins, failures, password resets).
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`, `app/services/security_service.py`

### GET `/rbac-audit-logs`
- **Endpoint:** `/rbac-audit-logs`
- **HTTP Method:** `GET`
- **Description:** Immutable RBAC permission denial audit log entries.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`, `app/database/repositories/rbac_audit_repository.py`

### GET `/rbac-audit-logs/{ticket_id}`
- **Endpoint:** `/rbac-audit-logs/{ticket_id}`
- **HTTP Method:** `GET`
- **Description:** RBAC audit events associated with a specific ticket ID.
- **Authentication Required:** Yes
- **User Roles:** All authenticated users (`EMPLOYEE`, `MANAGER`, `ADMIN`)
- **Related Services:** `app/main.py`

---

## 10. Enterprise Integration Adapters (`/servicenow`, `/microsoftgraph`, `/entra`)

### GET `/servicenow/incidents`
- **Endpoint:** `/servicenow/incidents`
- **HTTP Method:** `GET`
- **Description:** Fetches incidents directly from ServiceNow API (or mock adapter).
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "sys_id": "SYS998877",
      "number": "INC0099887",
      "short_description": "VPN issue",
      "state": "1"
    }
  ]
  ```
- **Related Services:** `app/main.py`, `app/services/servicenow_service.py`

### GET `/servicenow/incidents/{id}`
- **Endpoint:** `/servicenow/incidents/{id}`
- **HTTP Method:** `GET`
- **Description:** Fetches a specific ServiceNow incident by sys_id or number.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### POST `/servicenow/incidents`
- **Endpoint:** `/servicenow/incidents`
- **HTTP Method:** `POST`
- **Description:** Creates an incident directly in ServiceNow.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:**
  ```json
  {
    "short_description": "Printer offline on Floor 3",
    "description": "Network printer unresponsive",
    "category": "Hardware",
    "severity": 3
  }
  ```
- **Response Body:**
  ```json
  {
    "success": true,
    "sys_id": "SYS998877",
    "number": "INC0099887"
  }
  ```
- **Related Services:** `app/main.py`, `app/services/servicenow_service.py`

### GET `/servicenow/requests`
- **Endpoint:** `/servicenow/requests`
- **HTTP Method:** `GET`
- **Description:** Fetches ServiceNow service catalog requests.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/servicenow/requests/{id}`
- **Endpoint:** `/servicenow/requests/{id}`
- **HTTP Method:** `GET`
- **Description:** Details for a specific ServiceNow request.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/microsoftgraph/users`
- **Endpoint:** `/microsoftgraph/users`
- **HTTP Method:** `GET`
- **Description:** Microsoft Graph user directory entries (mock/live).
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/microsoftgraph/groups`
- **Endpoint:** `/microsoftgraph/groups`
- **HTTP Method:** `GET`
- **Description:** Microsoft Graph group membership data.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/entra/users`
- **Endpoint:** `/entra/users`
- **HTTP Method:** `GET`
- **Description:** Entra ID (Azure AD) user objects.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/entra/groups`
- **Endpoint:** `/entra/groups`
- **HTTP Method:** `GET`
- **Description:** Entra ID group objects.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

### GET `/entra/stats`
- **Endpoint:** `/entra/stats`
- **HTTP Method:** `GET`
- **Description:** Entra ID active directory user and group statistics.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Related Services:** `app/main.py`

---

## 11. Background Job Management (`/jobs`)

### GET `/jobs`
- **Endpoint:** `/jobs`
- **HTTP Method:** `GET`
- **Description:** Returns status of all background APScheduler jobs (`sla_monitor_job`, etc.).
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`
- **Request Body:** None
- **Response Body:**
  ```json
  [
    {
      "id": "sla_monitor_job",
      "name": "SLA Monitor Job",
      "next_run_time": "2026-07-26T12:31:00Z",
      "enabled": true
    }
  ]
  ```
- **Error Responses:**
  - `403 Forbidden`: Non-admin user.
- **Example Request:**
  ```bash
  curl -X GET http://localhost:8000/jobs \
    -H "Authorization: Bearer <access_token>"
  ```
- **Example Response:**
  ```json
  [ { "id": "sla_monitor_job", "enabled": true } ]
  ```
- **Related Services:** `app/main.py`, `app/jobs/`

---

### GET `/jobs/history`
- **Endpoint:** `/jobs/history`
- **HTTP Method:** `GET`
- **Description:** Execution log history of background jobs.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`
- **Related Services:** `app/main.py`

### POST `/jobs/run/{job_name}`
- **Endpoint:** `/jobs/run/{job_name}`
- **HTTP Method:** `POST`
- **Description:** Triggers an immediate manual run of a specific background job.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`
- **Related Services:** `app/main.py`

### POST `/jobs/enable/{job_name}`
- **Endpoint:** `/jobs/enable/{job_name}`
- **HTTP Method:** `POST`
- **Description:** Enables a scheduled background job.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`
- **Related Services:** `app/main.py`

### POST `/jobs/disable/{job_name}`
- **Endpoint:** `/jobs/disable/{job_name}`
- **HTTP Method:** `POST`
- **Description:** Disables a scheduled background job.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`
- **Related Services:** `app/main.py`

---

## 12. System Health & Observability (`/`, `/health`, `/ready`, `/metrics`, `/system-status`, `/health/servicenow`, `/metadata/health`)

### GET `/`
- **Endpoint:** `/`
- **HTTP Method:** `GET`
- **Description:** Service welcome banner and API version summary.
- **Authentication Required:** No
- **User Roles:** Public
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "message": "Welcome to Bridgestone IT AI Support Assistant API",
    "version": "1.0.0",
    "status": "healthy"
  }
  ```
- **Related Services:** `app/main.py`

---

### GET `/health`
- **Endpoint:** `/health`
- **HTTP Method:** `GET`
- **Description:** Lightweight Liveness probe for health checks.
- **Authentication Required:** No
- **User Roles:** Public
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "status": "healthy"
  }
  ```
- **Related Services:** `app/main.py`

---

### GET `/ready`
- **Endpoint:** `/ready`
- **HTTP Method:** `GET`
- **Description:** Kubernetes / load-balancer readiness probe. Verifies database connectivity and essential services before accepting incoming traffic.
- **Authentication Required:** No
- **User Roles:** Public
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "status": "ready",
    "database": "connected"
  }
  ```
- **Related Services:** `app/main.py`

---

### GET `/metrics`
- **Endpoint:** `/metrics`
- **HTTP Method:** `GET`
- **Description:** Returns Prometheus metric telemetry exposition text for scraping.
- **Authentication Required:** No
- **User Roles:** Public
- **Request Body:** None
- **Response Body:** Plaintext Prometheus metric series formatted as `text/plain; version=0.0.4`.
- **Related Services:** `app/main.py`, `app/core/metrics.py`

---

### GET `/system-status`
- **Endpoint:** `/system-status`
- **HTTP Method:** `GET`
- **Description:** Deep system health diagnostic inspecting Database, Gemini AI Provider, ServiceNow Adapter, Graph Adapter, AD Adapter, and Scheduler status.
- **Authentication Required:** Yes
- **User Roles:** `ADMIN`, `MANAGER`
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "status": "healthy",
    "database": "healthy",
    "gemini": "healthy",
    "adapters": {
      "ServiceNow": { "status": "healthy", "latency": 0.12, "details": "OAuth2 authenticated." },
      "Microsoft Graph": { "status": "healthy", "latency": 0.0, "details": "Mock Mode active." },
      "Active Directory": { "status": "healthy", "latency": 0.0, "details": "Mock Mode active." }
    },
    "scheduler": { "running": true, "jobs": 1 }
  }
  ```
- **Related Services:** `app/main.py`

---

### GET `/health/servicenow`
- **Endpoint:** `/health/servicenow`
- **HTTP Method:** `GET`
- **Description:** Health check endpoint specifically for the ServiceNow integration adapter.
- **Authentication Required:** No
- **User Roles:** Public
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "status": "healthy",
    "adapter": "ServiceNow",
    "use_mock": false,
    "instance_url": "https://dev12345.service-now.com"
  }
  ```
- **Related Services:** `app/main.py`, `app/services/servicenow_service.py`

---

### GET `/metadata/health`
- **Endpoint:** `/metadata/health`
- **HTTP Method:** `GET`
- **Description:** Returns ServiceNow metadata cache health, validation TTL status, and cached category counts.
- **Authentication Required:** No
- **User Roles:** Public
- **Request Body:** None
- **Response Body:**
  ```json
  {
    "status": "healthy",
    "cache_valid": true,
    "ttl_seconds_remaining": 3450,
    "cached_categories_count": 12
  }
  ```
- **Related Services:** `app/main.py`, `app/services/servicenow_metadata_cache.py`, `app/services/servicenow_metadata_validator.py`

---

## Error Handling Summary

All API endpoints follow standardized FastAPI error response schemas:

```json
{
  "detail": "Human-readable error explanation message",
  "error_code": "ExceptionClassName"
}
```

| HTTP Code | Error | Cause |
|---|---|---|
| `400` | Bad Request | Missing mandatory fields, prompt injection detected, or invalid query value |
| `401` | Unauthorized | Missing, expired, or invalid JWT bearer token |
| `403` | Forbidden | Authenticated user lacks required role (`EMPLOYEE` attempting `ADMIN` action) |
| `404` | Not Found | Target resource ID (ticket, comment, article) does not exist |
| `429` | Too Many Requests | Endpoint rate limit exceeded |
| `500` | Internal Server Error | Unhandled server exception |
