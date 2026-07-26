# Comprehensive System Testing Checklist

> **Project:** Bridgestone IT AI Assistant · **Last updated:** 2026-07-26  
> **Target Version:** 1.0.0 Enterprise POC  
> **Automated Suite Execution:** `pytest tests/ -v` (690+ passing unit and integration tests)

This document provides the complete end-to-end testing matrix for the Bridgestone IT AI Support platform.

---

## Default Test Credentials

| Username | Role | Password | Accessible Views / Features |
|---|---|---|---|
| `employee` | `EMPLOYEE` | `employeepassword` | AI Assistant Chat, My Requests, Catalog |
| `manager` | `MANAGER` | `managerpassword` | AI Assistant Chat, My Requests, Catalog, Manager Portal |
| `admin` | `ADMIN` | `adminpassword` | Full system access: ITSM Queue, Analytics, KB Admin, Jobs, Security Audit |

---

## Test Execution Matrix

### 1. Authentication

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-AUTH-001** | Valid User Login | 1. Navigate to `/login`.<br>2. Enter valid credentials (`employee` / `employeepassword`).<br>3. Click "Sign In". | Authenticates successfully, receives JWT access and refresh tokens, redirects to `/`. | | Pass |
| **TC-AUTH-002** | Invalid Password Attempt | 1. Enter username `employee`.<br>2. Enter password `wrongpassword`.<br>3. Click "Sign In". | Returns HTTP 401 error: "Incorrect username or password". Security log records `FAILED_LOGIN`. | | Pass |
| **TC-AUTH-003** | Deactivated User Account | 1. Attempt login with a deactivated user account. | Returns HTTP 400 error: "User account is deactivated". | | Pass |
| **TC-AUTH-004** | Token Refresh | 1. Call `POST /auth/refresh` with valid refresh token. | Returns new JWT access token with valid expiration. | | Pass |
| **TC-AUTH-005** | User Logout | 1. Log in to dashboard.<br>2. Click "Sign Out" button. | Invalidates session, records `LOGOUT` in security event log, redirects to `/login`. | | Pass |

---

### 2. Authorization & Role-Based Access Control (RBAC)

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-RBAC-001** | Employee Sidebar Navigation | 1. Log in as `employee`.<br>2. Inspect navigation sidebar. | Only "AI Assistant" and "My Requests" are visible. "Manager Portal", "ITSM Queue", "Analytics", and "KB Admin" are hidden. | | Pass |
| **TC-RBAC-002** | Manager Sidebar Navigation | 1. Log in as `manager`.<br>2. Inspect navigation sidebar. | "Manager Portal" tab is visible alongside AI Assistant and My Requests. "ITSM Queue" and "KB Admin" are hidden. | | Pass |
| **TC-RBAC-003** | Admin Full Sidebar Navigation | 1. Log in as `admin`.<br>2. Inspect navigation sidebar. | All navigation tabs (AI Assistant, My Requests, Manager Portal, ITSM Queue, Executive Dashboard, KB Admin) are visible. | | Pass |
| **TC-RBAC-004** | Direct URL Route Protection | 1. Log in as `employee`.<br>2. Manually navigate to `/admin` or `/analytics`. | System denies access, redirects user to unauthorized notification, or displays 403. | | Pass |
| **TC-RBAC-005** | API Role Denial | 1. Obtain JWT token for `employee`.<br>2. Send HTTP request to `GET /api/itsm/admin-queue`. | FastAPI returns HTTP 403 Forbidden. `RBACAuditLog` entry created with `ACCESS_DENIED`. | | Pass |
| **TC-RBAC-006** | Ticket Resource Scoping | 1. Log in as `employee`.<br>2. Request ticket details created by another user (`INC0000001`). | Access denied with HTTP 403 Forbidden or empty payload. Users can only view their own tickets. | | Pass |

---

### 3. AI Support Chat & Intent Routing

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-AI-001** | General IT Troubleshooting | 1. Open AI Assistant chat.<br>2. Type "My VPN is not connecting from home". | Intent classified as `VPN`. Graph executes diagnostic steps (adapter restart, certificate check). | | Pass |
| **TC-AI-002** | Direct Ticket Command | 1. Type "Create a ticket for my printer issue". | Intent router detects `TICKET_COMMAND`. Skips troubleshooting and prompts ticket creation confirmation. | | Pass |
| **TC-AI-003** | Restart Session Command | 1. Type "restart". | Conversation state machine resets to initial state. Chat history cleared. | | Pass |
| **TC-AI-004** | Cancel Command | 1. In diagnostic flow, type "cancel". | Current troubleshooting workflow is aborted. Session returns to neutral state. | | Pass |
| **TC-AI-005** | Check Ticket Status Command | 1. Type "check ticket status". | Bot queries active user tickets and displays latest ServiceNow status and assignment. | | Pass |
| **TC-AI-006** | Resolution Keyword Detection | 1. In diagnostic flow, type "it is working now". | State machine detects resolution keyword, transitions to `RESOLVED` phase, and offers resolution confirmation. | | Pass |
| **TC-AI-007** | Multilingual & Casual Language | 1. Type "vpn dead pls fix". | Intent router correctly identifies category `VPN` and maintains empathetic support persona. | | Pass |
| **TC-AI-008** | Fallback Model Resilience | 1. Simulate primary LLM rate limit (429). | Provider automatically falls back from primary to secondary flash-lite model without user error. | | Pass |

---

### 4. ServiceNow Integration & Field Mapping

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-SN-001** | Standard Incident Creation | 1. Confirm ticket creation for VPN issue. | Ticket created in DB and ServiceNow with category `Network`, subcategory `VPN-Global Protect`, assigned to `Network Team`. | | Pass |
| **TC-SN-002** | Printer Offline Mapping | 1. Submit printer offline issue. | `IncidentEnrichmentService` maps category to `Printer`, subcategory to `Printer Offline`. | | Pass |
| **TC-SN-003** | Outlook Issues Mapping | 1. Submit Outlook startup crash issue. | Mapped to category `Microsoft 365`, subcategory `Outlook Not Working`, CMDB CI `Microsoft Office Suite`. | | Pass |
| **TC-SN-004** | Software Service Request Classification | 1. Request software installation ("Install VS Code"). | Classified as `SERVICE_REQUEST`. Request type set to `SERVICE_REQUEST`, status set to `WAITING_MANAGER`. | | Pass |
| **TC-SN-005** | Metadata Validator Runtime Correction | 1. Pass an invalid subcategory string. | `RuntimeValidator` flags invalid subcategory, logs warning, and sets fallback assignment group. | | Pass |
| **TC-SN-006** | Mock Adapter Fallback | 1. Set `USE_MOCK_SERVICENOW=true`.<br>2. Create a ticket. | Mock adapter generates deterministic `INC0071800` sys_id and valid ServiceNow payload. | | Pass |

---

### 5. Manager Approval Workflow

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-MGR-001** | Service Request Submission | 1. As `employee`, request privileged software (e.g., VS Code). | Ticket created with status `WAITING_MANAGER` and approval_status `PENDING`. | | Pass |
| **TC-MGR-002** | Manager Pending Approval Queue | 1. Log in as `manager`.<br>2. Open Manager Portal. | Newly created privileged ticket appears in Pending Approvals list with employee name, category, and details. | | Pass |
| **TC-MGR-003** | Manager Approve Action | 1. As `manager`, click "Approve".<br>2. Enter approval notes: "Approved for project". | Ticket status updates to `READY_FOR_ADMIN`, approval_status updates to `APPROVED`, ticket moves to Approved Requests tab. | | Pass |
| **TC-MGR-004** | Manager Reject Action | 1. As `manager`, click "Reject".<br>2. Enter rejection reason. | Ticket status updates to `REJECTED`. Employee is notified via in-app notification. | | Pass |
| **TC-MGR-005** | Approval History Persistence | 1. Refresh Manager Portal. | Approved request remains visible in "Approved Requests" tab displaying Approval Time, Approved By, and Notes. | | Pass |

---

### 6. Admin Queue & Temporary Admin Access (LAPS Mock)

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-ADM-001** | Admin Processing Queue View | 1. Log in as `admin`.<br>2. Open ITSM Admin Queue. | Manager-approved ticket appears with status `READY_FOR_ADMIN` and "Grant Temporary Admin Access" button. | | Pass |
| **TC-ADM-002** | Grant Admin Access Execution | 1. Click "Grant Temporary Admin Access". | Ticket status changes to `ACCESS_GRANTED`. Enterprise Admin Access Card is generated for ticket session. | | Pass |
| **TC-ADM-003** | Admin Access Card Display (Employee View) | 1. Switch to `employee` view on ticket. | Enterprise Admin Access Card displays status `ACTIVE`, Username `.\Administrator`, masked password, and 15-min timer. | | Pass |
| **TC-ADM-004** | Password Unmasking & Countdown | 1. Click "Show Password" button on Admin Access Card. | Password `Temp@4821#` is unmasked. Countdown timer decreases in real time from `15:00`. | | Pass |
| **TC-ADM-005** | Complete Software Installation | 1. As `admin`, click "Mark Completed". | Ticket status transitions to `COMPLETED`. Temporary access card expires. | | Pass |

---

### 7. Knowledge Base Administration

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-KB-001** | Create Article Draft | 1. Log in as `admin`.<br>2. Navigate to KB Admin.<br>3. Submit new article form. | Article saved with status `DRAFT`. Appears in KB article list. | | Pass |
| **TC-KB-002** | Publish KB Article | 1. Select draft article.<br>2. Click "Publish". | Status updates to `PUBLISHED`. Article becomes indexed for AI troubleshooting. | | Pass |
| **TC-KB-003** | AI Retrieval of Published Article | 1. Ask chat a question matching published KB title/category. | AI includes resolution steps directly from published KB article. | | Pass |
| **TC-KB-004** | Article Versioning | 1. Edit published article and save. | Version increments (e.g. v1.0 -> v1.1). Past version saved in version history. | | Pass |
| **TC-KB-005** | Archive KB Article | 1. Click "Archive" on published article. | Article status set to `ARCHIVED`. AI no longer retrieves it for troubleshooting. | | Pass |

---

### 8. UI & User Experience

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-UI-001** | Responsive Navigation Drawer | 1. Resize browser window to mobile width (<768px). | Desktop sidebar collapses into mobile drawer menu. | | Pass |
| **TC-UI-002** | Dark/Light Mode Theme Toggle | 1. Click theme toggle button in header. | UI theme toggles cleanly between dark and light mode without broken styling. | | Pass |
| **TC-UI-003** | Executive Analytics Charts | 1. Open Executive Analytics view as `admin`. | Recharts components render ticket volume, category distribution, and SLA charts. | | Pass |
| **TC-UI-004** | Chat Message Auto-scroll | 1. Send multiple messages in AI Assistant chat. | Chat window auto-scrolls smoothly to keep latest agent message in view. | | Pass |
| **TC-UI-005** | Interactive Notification Badge | 1. Perform action triggering notification.<br>2. Check top header. | Bell icon badge increments count and displays drop-down notification list. | | Pass |
| **TC-UI-006** | Ticket Status Pill Color Coding | 1. View tickets list. | Status badges display distinct colors (`NEW`=Blue, `WAITING_MANAGER`=Amber, `ACCESS_GRANTED`=Emerald, `REJECTED`=Red). | | Pass |

---

### 9. API Endpoint Testing

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-API-001** | `/health` Endpoint | 1. Send `GET /health`. | Returns HTTP 200 `{"status": "healthy"}`. | | Pass |
| **TC-API-002** | `/system-status` Deep Diagnostics | 1. Send `GET /system-status` with admin token. | Returns status of DB, Gemini, ServiceNow, Graph, AD, and Scheduler. | | Pass |
| **TC-API-003** | `/tickets` List Filtering | 1. Send `GET /tickets?status=WAITING_MANAGER`. | Returns list filtered exclusively to tickets with `WAITING_MANAGER` status. | | Pass |
| **TC-API-004** | `/tickets/{id}/comments` Post | 1. Send `POST /tickets/INC0071800/comments` with text payload. | Appends comment, returns comment ID and timestamp. | | Pass |
| **TC-API-005** | `/sla/dashboard-metrics` | 1. Send `GET /sla/dashboard-metrics`. | Returns aggregated SLA state counts and compliance percentage. | | Pass |
| **TC-API-006** | `/api/analytics/dashboard` | 1. Send `GET /api/analytics/dashboard?time_filter=month`. | Returns ticket volume by day, category breakdown, and team metrics. | | Pass |
| **TC-API-007** | `/jobs` Scheduler List | 1. Send `GET /jobs` as admin. | Returns active APScheduler jobs (`sla_monitor_job`) with next run time. | | Pass |
| **TC-API-008** | `/servicenow/incidents` Adapter | 1. Send `GET /servicenow/incidents` as admin. | Returns live/mock ServiceNow incident objects. | | Pass |

---

### 10. Error Handling & Invalid Inputs

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-ERR-001** | Empty Chat Message Payload | 1. Send `POST /chat` with `{"message": ""}`. | Returns HTTP 400 error: "Message content cannot be empty". | | Pass |
| **TC-ERR-002** | Missing Mandatory Ticket Fields | 1. Send `POST /ticket` without `category`. | Returns HTTP 400 error: "category is required". | | Pass |
| **TC-ERR-003** | Non-existent Ticket ID Lookup | 1. Send `GET /tickets/INC9999999/details`. | Returns HTTP 404 Not Found: "Ticket not found". | | Pass |
| **TC-ERR-004** | Malformed JSON Payload | 1. Send malformed JSON string to API. | Returns HTTP 422 Unprocessable Entity with validation details. | | Pass |
| **TC-ERR-005** | Invalid CSAT Rating Range | 1. Submit `POST /tickets/INC0071800/csat` with `rating=10`. | Returns HTTP 400 error: "Rating must be between 1 and 5". | | Pass |
| **TC-ERR-006** | Prompt Injection Prevention | 1. Send high-risk prompt injection string to chat. | PromptGuard intercepts request, blocks execution, and returns HTTP 400. | | Pass |

---

### 11. Edge Cases & Failure Recovery

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-EDGE-001** | ServiceNow Offline Fallback | 1. Simulate ServiceNow connection timeout. | System logs failure, falls back to local database persistence, ticket creation succeeds without crash. | | Pass |
| **TC-EDGE-002** | Duplicate Ticket Detection | 1. Create ticket for "VPN connection issue".<br>2. Submit identical ticket. | Semantic duplicate check detects match, warns user, and offers link to existing ticket. | | Pass |
| **TC-EDGE-003** | SLA Breach Escalation Trigger | 1. Fast-forward ticket time past SLA deadline. | SLA monitor job detects breach, updates state to `BREACHED`, creates `SlaEscalationHistory` entry, and notifies admin. | | Pass |
| **TC-EDGE-004** | Simultaneous Manager Approval | 1. Send concurrent approve requests for same ticket. | First request succeeds (`READY_FOR_ADMIN`), second request returns graceful idempotent status. | | Pass |
| **TC-EDGE-005** | Expired Temporary Credentials | 1. Wait 15 minutes after admin access grant. | LAPS countdown reaches 00:00. Credentials card updates status to `EXPIRED`. | | Pass |

---

### 12. Performance & Rate Limiting

| Test ID | Description | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-PERF-001** | Login Rate Limiting | 1. Send 12 rapid `POST /auth/login` requests within 30 seconds. | 11th request triggers HTTP 429 Too Many Requests rate limit warning. | | Pass |
| **TC-PERF-002** | Support Chat Rate Limiting | 1. Send 35 rapid chat requests within 60 seconds. | Exceeds 30 req/min limit, returns HTTP 429 error. | | Pass |
| **TC-PERF-003** | Parallel Request Handling | 1. Execute 20 concurrent user chat requests. | System handles requests asynchronously without thread deadlock or request drops. | | Pass |
| **TC-PERF-004** | API Response Latency | 1. Benchmark non-LLM read endpoints (`GET /tickets`). | Average response latency is under 50ms. | | Pass |

---

## Related Documentation

- [System Architecture](./architecture.md) — Enterprise component design
- [AI Workflow & LangGraph](./ai-workflow.md) — Node execution pipeline
- [ServiceNow Integration Guide](./servicenow.md) — Metadata mapping specifications
- [API Reference](./API.md) — Comprehensive endpoint specifications
