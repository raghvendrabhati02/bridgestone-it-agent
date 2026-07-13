# Architecture – Bridgestone IT Agent

> **Version:** 1.0.0 | **Last updated:** 2026-07-11

---

## 1. Overview

Bridgestone IT Agent is a containerised, enterprise-grade AI IT-support platform.  
It consists of four runtime tiers communicating over a private Docker bridge network.

```mermaid
graph TD
    Employee([Employee])
    Manager([Manager])
    Admin([Admin])

    subgraph Edge ["Edge Layer"]
        Nginx[NGINX Reverse Proxy]
    end

    subgraph Frontend ["Presentation Tier – Next.js 15"]
        FE[Next.js Application :3000]
    end

    subgraph Backend ["Application Tier – FastAPI / Python 3.12"]
        API[FastAPI :8000]
    end

    subgraph AI ["Intelligence Layer"]
        ConvSvc[ConversationService]
        IntentRouter[IntentRouter]
        KnowledgeEngine[KnowledgeEngine]
        GeminiSvc[GeminiService]
        TroubleshootingSvc[TroubleshootingService]
    end

    subgraph Storage ["Storage Tier"]
        PG[(PostgreSQL)]
        SQLite[(SQLite – Dev Fallback)]
    end

    subgraph Integrations ["External Integrations"]
        SN[ServiceNow REST]
        MSGraph[Microsoft Graph API]
        ADAP[Active Directory]
    end

    Employee --> Nginx
    Manager --> Nginx
    Admin --> Nginx
    Nginx --> FE
    FE --> API
    API --> ConvSvc
    ConvSvc --> IntentRouter
    ConvSvc --> KnowledgeEngine
    ConvSvc --> GeminiSvc
    ConvSvc --> TroubleshootingSvc
    API --> PG
    API --> SQLite
    API --> SN
    API --> MSGraph
    API --> ADAP
```

---

## 2. Tier Details

### 2.1 Edge Layer – NGINX

| Attribute | Value |
|-----------|-------|
| Image | `nginx:stable-alpine` |
| Role | TLS termination, path-based routing |
| Routes | `/` → Frontend `:3000` · `/api/` → Backend `:8000` |
| Config | `infrastructure/nginx/` |

NGINX is the single public entrypoint. All backend traffic flows through `/api/` path rewrites; the frontend serves everything else.

---

### 2.2 Presentation Tier – Next.js Frontend

| Attribute | Value |
|-----------|-------|
| Framework | Next.js 15, React, TypeScript |
| Port | 3000 |
| Config | `NEXT_PUBLIC_API_URL` environment variable |
| Auth | JWT bearer token in `localStorage` |

**Key UI Components**

| Component | Purpose |
|-----------|---------|
| `AppShell.tsx` | Navigation shell, role-based sidebar |
| `SupportChatView.tsx` | AI chat interface |
| `ITSMQueueView.tsx` | Admin/Manager ticket queue |
| `ManagerPortal.tsx` | Approval workflow portal |
| `KnowledgeBase.tsx` | KB article viewer and editor |
| `AnalyticsView.tsx` | Dashboard metrics and charts |
| `DeviceDashboard.tsx` | Enterprise device management |
| `ExecutionCenter.tsx` | IT action execution history |
| `MyTicketsView.tsx` | Employee ticket self-service |

---

### 2.3 Application Tier – FastAPI Backend

| Attribute | Value |
|-----------|-------|
| Framework | FastAPI, Python 3.12 |
| Port | 8000 |
| Entry point | `app/main.py` |
| ASGI server | Uvicorn |

**Request lifecycle:**

```mermaid
sequenceDiagram
    participant C as Client
    participant MW as Middleware
    participant EP as Endpoint
    participant SVC as Service Layer
    participant DB as Database

    C->>MW: HTTP Request + Bearer token
    MW->>MW: Extract session_id, correlation_id, JWT
    MW->>MW: Increment Prometheus counters
    MW->>EP: Forwarded request
    EP->>SVC: Business logic call
    SVC->>DB: SQLAlchemy ORM query
    DB-->>SVC: Result
    SVC-->>EP: Response payload
    EP-->>MW: HTTP Response
    MW->>MW: Log duration + status code
    MW-->>C: Final response
```

**Middleware chain (applied in order):**

1. `CORSMiddleware` – allowlist from `CORS_ORIGINS` env var
2. `monitor_requests` – request ID, correlation ID, JWT extraction, Prometheus metrics, structured JSON logging
3. `global_exception_handler` – converts all unhandled exceptions to `{"detail":..., "error_code":...}` JSON

---

### 2.4 Intelligence Layer – AI Pipeline

The AI pipeline is **stateless at the service level**. All conversation state lives in `ConversationState` objects serialised to the database.

```mermaid
flowchart TD
    A[User Message] --> B[IntentRouter]
    B -->|TICKET_COMMAND| C[TicketOrchestrator - creates ticket immediately]
    B -->|RESTART| D[Restart Handler]
    B -->|CANCEL| E[Cancel Handler]
    B -->|STATUS| F[Status Handler]
    B -->|RESOLVED_KEYWORD| G[Resolution Handler]
    B -->|IT_ISSUE| H[ConversationService Phase Router]

    H -->|UNDERSTANDING| I[KnowledgeEngine Search]
    I --> J[TroubleshootingService]
    J --> K[Step-by-step guidance loop]
    K -->|Not resolved| L[TicketOrchestrator]
    K -->|Resolved| M[Resolution ACK]

    H -->|WAITING_ACTION_CONFIRMATION| N[ApprovalService]
    N -->|Approved by Manager or Admin| O[ActionEngine]
    N -->|Rejected| P[Cancel flow]
    N -->|EMPLOYEE attempt| Q[RBAC ACCESS_DENIED]
```

**IntentRouter priority order (deterministic, never reordered):**

1. `TICKET_COMMAND` – "create ticket", "raise incident", "open a ticket", "escalate"
2. `RESTART` – "restart", "start over", "new issue"
3. `CANCEL` – "cancel", "abort", "stop", "never mind"
4. `STATUS` – "ticket status", "check ticket", "my ticket"
5. `RESOLVED_KEYWORD` – "working", "fixed", "solved", "issue resolved"
6. `IT_ISSUE` – keyword/regex classification into category
7. `GENERAL` – fallback, routed to Gemini free conversation

**IT Issue Categories:**

| Category | Trigger Keywords |
|----------|-----------------|
| `VPN` | vpn, global protect, remote access |
| `OUTLOOK` | outlook, email, mailbox, exchange |
| `PRINTER` | printer, printing, print queue, spooler |
| `SOFTWARE_INSTALLATION` | install, chrome, zoom, teams, software |
| `NETWORK` | wifi, network, internet, connectivity |
| `PASSWORD_RESET` | password, reset password, locked out |
| `SAP` | sap, erp, sap gui |
| `GENERAL` | anything else |

---

### 2.5 Storage Tier

| Database | Use case |
|----------|----------|
| PostgreSQL (primary) | All persistent data: tickets, users, sessions, audit logs, SLA records |
| SQLite (dev fallback) | Automatic fallback when PostgreSQL is unreachable |

PostgreSQL connection pooling (`connection.py`):

| Setting | Value |
|---------|-------|
| `pool_size` | 20 |
| `max_overflow` | 10 |
| `pool_timeout` | 30 s |
| `pool_recycle` | 1800 s |
| `pool_pre_ping` | `True` |

SQLite settings: WAL journal mode, NORMAL synchronicity, `NullPool`.

---

## 3. Background Jobs (APScheduler)

| Job | Frequency | Purpose |
|-----|-----------|---------|
| `sla_monitor_job` | Every 60 s | Evaluates all open tickets for SLA state transitions and breach escalations |
| `auto_close_job` | Configurable | Auto-closes tickets resolved beyond idle threshold |
| `cleanup_job` | Configurable | Removes stale sessions and aged data |
| `notification_job` | Configurable | Dispatches pending notification records |

---

## 4. ITSM Ticket Lifecycle

```mermaid
stateDiagram-v2
    [*] --> NEW : INCIDENT created
    [*] --> WAITING_MANAGER : SERVICE_REQUEST or PRIVILEGED_ACTION

    WAITING_MANAGER --> APPROVED : Manager approves
    WAITING_MANAGER --> REJECTED : Manager rejects
    APPROVED --> ASSIGNED : Admin assigns engineer
    NEW --> ASSIGNED : Admin assigns engineer
    ASSIGNED --> IN_PROGRESS : Engineer begins work
    IN_PROGRESS --> PENDING : Waiting on user info
    PENDING --> IN_PROGRESS : User responds
    IN_PROGRESS --> RESOLVED : Engineer marks resolved
    RESOLVED --> CLOSED : Auto-close or explicit close
    RESOLVED --> IN_PROGRESS : Reopened by user
    CLOSED --> [*]
    REJECTED --> [*]
```

**ITSM Classification Rules (priority order):**

1. Category/description matches privileged keywords → `PRIVILEGED_ACTION`
2. Category is in service-catalog set → `SERVICE_REQUEST`
3. Anything else → `INCIDENT`

---

## 5. SLA Escalation Engine

| SLA State | Trigger |
|-----------|---------|
| `HEALTHY` | < 75% SLA window consumed |
| `WARNING_75` | 75–89% consumed |
| `WARNING_90` | 90–99% consumed |
| `BREACHED` | 100%+ consumed |
| `ESCALATED_LEVEL_1` | Immediately on breach |
| `ESCALATED_LEVEL_2` | Breach + 30 minutes |
| `ESCALATED_LEVEL_3` | Breach + 60 minutes |

Notification recipients per state:

| State | Recipients |
|-------|-----------|
| `WARNING_75` | Manager |
| `WARNING_90` | Manager, Admin |
| `BREACHED` and above | Manager, Admin |

---

## 6. External Integrations

| Integration | Adapter class | Default mode |
|-------------|---------------|-------------|
| ServiceNow REST API | `ServiceNowAdapter` | Mock |
| Microsoft Graph API | `MicrosoftGraphAdapter` | Mock |
| Azure AD / Entra ID | `ActiveDirectoryAdapter` | Mock |
| VPN Gateway | `VPNAdapter` | Mock |

All adapters expose `is_mock` detection and fall back gracefully to mock data when real credentials are absent.

---

## 7. Observability

| Signal | Implementation |
|--------|---------------|
| Structured logs | JSON format with `request_id`, `correlation_id`, `session_id`, `user`, `role`, `endpoint` |
| Prometheus metrics | `GET /metrics` – counters and histograms for HTTP, DB, LLM, security events |
| Health check | `GET /health` – returns `{"status": "healthy"}` |
| System status | `GET /system-status` – deep check of DB, Gemini, adapters, scheduler |

---

## 8. Directory Structure

```
bridgestone-it-agent/
├── backend/
│   ├── app/
│   │   ├── adapters/          # ServiceNow, Graph, AD, VPN adapters
│   │   ├── agents/            # Specialised LLM agent implementations
│   │   ├── api/               # Router modules: auth, analytics, devices, executions
│   │   ├── core/              # Security, JWT, RBAC, metrics, logging context
│   │   ├── database/          # SQLAlchemy models, connection, session
│   │   │   └── models/        # ticket, user, audit_log, sla, device, etc.
│   │   ├── integrations/      # ServiceNow integration models
│   │   ├── jobs/              # APScheduler job definitions
│   │   ├── services/          # All business logic services
│   │   └── tools/             # IT tool implementations (VPN, Outlook, printer, etc.)
│   └── knowledge_base/        # JSON knowledge-base articles by category
├── frontend/
│   └── src/
│       ├── app/               # Next.js App Router pages
│       ├── components/        # Feature-level UI components
│       └── lib/               # API client, utilities, auth helpers
├── infrastructure/
│   ├── compose/               # docker-compose.dev.yml / docker-compose.prod.yml
│   ├── docker/                # Per-service Dockerfiles
│   ├── env/                   # dev.env / prod.env environment files
│   ├── monitoring/            # Prometheus and Grafana configs
│   └── nginx/                 # NGINX reverse proxy config
├── docs/                      # All project documentation
└── knowledge_base/            # KB JSON articles (VPN, Outlook, Printer, SAP, etc.)
```
