# Bridgestone IT Agent — API Documentation

This document describes the REST API endpoints, authentication mechanisms, request/response JSON schemas, and HTTP status codes for the Bridgestone IT Agent backend.

---

## 1. Authentication Endpoints

All application API endpoints (excluding `/api/auth/register` and `/api/auth/token`) require a valid JSON Web Token (JWT) passed in the `Authorization: Bearer <token>` header.

### A. Register User
Creates a new platform user profile.
* **Method & Path:** `POST /api/auth/register`
* **Request Body Schema:**
  ```json
  {
    "username": "rahul_sharma",
    "password": "strongpassword123",
    "role": "EMPLOYEE"
  }
  ```
* **Response Schema (201 Created):**
  ```json
  {
    "id": 1,
    "username": "rahul_sharma",
    "role": "EMPLOYEE",
    "is_active": true
  }
  ```

### B. Authenticate / Retrieve Token
Verifies password credentials and issues a JWT token.
* **Method & Path:** `POST /api/auth/token`
* **Request Body Schema (Form URL Encoded):**
  * `username`: string
  * `password`: string
* **Response Schema (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```

---

## 2. Conversational Agent Endpoints

### Send Message / Chat Turn
Feeds a message into the LangGraph network under a specific session.
* **Method & Path:** `POST /api/chat`
* **Request Headers:** `Authorization: Bearer <token>`
* **Request Body Schema:**
  ```json
  {
    "session_id": "sess-e2e-journey-01",
    "message": "My VPN access is disabled on Pune gateway"
  }
  ```
* **Response Schema (200 OK):**
  ```json
  {
    "session_id": "sess-e2e-journey-01",
    "category": "VPN",
    "action": "REQUEST_APPROVAL",
    "response": "⚠️ **Approval Required**\n\nThe action **Vpn Access Restoration** requires your explicit approval before execution.",
    "ticket_created": false,
    "ticket_id": null,
    "servicenow_id": null,
    "assigned_team": null,
    "priority": null,
    "approval_required": true,
    "approval_status": "PENDING",
    "recommended_action": "VPN_ACCESS_RESTORATION"
  }
  ```

---

## 3. Incident Management Endpoints

### A. List Incidents
Retrieves all support tickets with optional filtering.
* **Method & Path:** `GET /tickets`
* **Query Parameters:** `status` (string), `priority` (string), `category` (string), `assigned_team` (string)
* **Response Schema (200 OK):**
  ```json
  [
    {
      "ticket_id": "INC000001",
      "category": "VPN",
      "description": "VPN connection drops every 5 minutes",
      "priority": "HIGH",
      "status": "OPEN",
      "assigned_team": "Network Team",
      "created_by": "Rahul Sharma",
      "created_at": "2026-06-29T11:00:00Z"
    }
  ]
  ```

### B. Reopen Incident
Reopens a resolved incident ticket. Only employees or assignees can trigger this.
* **Method & Path:** `POST /tickets/{ticket_id}/reopen`
* **Response Schema (200 OK):**
  ```json
  {
    "status": "success",
    "message": "Ticket INC000001 reopened and transitioned to IN_PROGRESS."
  }
  ```

---

## 4. Administrative & Observability Endpoints

### A. List Audit Logs
Returns historical audit trail events (ADMIN role only).
* **Method & Path:** `GET /audit-logs`
* **Response Schema (200 OK):**
  ```json
  [
    {
      "id": 44,
      "session_id": "sess-e2e-journey-01",
      "user_message": "My VPN access is disabled on Pune gateway",
      "category": "VPN",
      "decision": "REQUEST_APPROVAL",
      "created_at": "2026-06-29T11:04:05Z"
    }
  ]
  ```

### B. List RBAC Audit Events
Returns access permission history events (ADMIN role only).
* **Method & Path:** `GET /rbac-audit-logs`
* **Response Schema (200 OK):**
  ```json
  [
    {
      "id": 12,
      "timestamp": "2026-06-29T11:04:05Z",
      "user": "employee",
      "role": "EMPLOYEE",
      "action": "ACCESS_DENIED",
      "ticket_id": "INC000005",
      "details": {
        "reason": "RBAC_DENIED",
        "required_action": "approve_privileged_action"
      }
    }
  ]
  ```