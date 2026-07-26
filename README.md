# Bridgestone IT AI Assistant

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16.2-000000?style=for-the-badge&logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_Pipeline-FF6B35?style=for-the-badge)
![ServiceNow](https://img.shields.io/badge/ServiceNow-Live_Integration-62D84E?style=for-the-badge&logo=servicenow&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

**An agentic AI-powered IT support system with live ServiceNow integration, role-based access control, SLA monitoring, and a multi-portal Next.js dashboard — built as a proof-of-concept for enterprise IT operations.**

[Problem](#-problem-statement) • [Highlights](#-project-highlights) • [Architecture](#-system-architecture) • [Installation](#-installation-guide) • [API](#-api-documentation) • [Security](#-security-features) • [Demo](#-demo-flow)

</div>

---

## 📌 Problem Statement

IT helpdesks in large organisations face high ticket volumes, repetitive first-line issues, slow triage, and manual ServiceNow data entry. Privileged software installations require multi-step human approval chains with no automated tracking, and SLA breaches often go undetected until it is too late.

**The result:** Delayed resolutions, missed SLAs, and a poor experience for both employees and IT staff.

---

## 🚀 Project Highlights

- **Conversational AI troubleshooting** — employees describe their issue in plain English; the AI agent diagnoses and guides resolution step by step.
- **Automatic ServiceNow incident creation** — incidents are classified, enriched, and submitted to a live ServiceNow instance via OAuth2, with field values validated against the live instance metadata before submission.
- **Dual-approval workflow** — privileged software requests (e.g. VS Code, SAP GUI) are routed through Manager → IT Admin approval before access is granted.
- **Role-separated portals** — dedicated UIs for employees, managers, and IT admins, each showing only what is relevant to their role.
- **Real-time SLA monitoring** — an APScheduler job evaluates every open ticket every 60 seconds and escalates through seven states automatically.
- **Prompt injection protection** — a three-tier risk classifier screens every user message before it reaches the AI pipeline.

---

## 🏆 Project Achievements

The following capabilities are fully implemented and functional in this POC:

| Area | Status |
|---|---|
| LangGraph agentic pipeline (18 nodes) | ✅ Complete |
| AI classification with Gemini (primary) and Claude (fallback) | ✅ Complete |
| Live ServiceNow OAuth2 incident creation | ✅ Complete |
| ServiceNow metadata validation and field mapping | ✅ Complete |
| Manager → Admin dual-approval workflow | ✅ Complete |
| Mock temporary admin credential delivery (LAPS placeholder) | ✅ Complete |
| Four-role RBAC with JWT authentication | ✅ Complete |
| SLA monitoring with seven escalation states | ✅ Complete |
| Prompt injection guard (three-tier classifier) | ✅ Complete |
| Sliding-window rate limiting | ✅ Complete |
| Structured JSON logging with correlation IDs | ✅ Complete |
| Immutable RBAC audit log | ✅ Complete |
| Analytics dashboard (Recharts) | ✅ Complete |
| Knowledge base with AI-assisted article suggestions | ✅ Complete |
| Automatic database schema migration on startup | ✅ Complete |

---

## 🎬 Demo Flow

The following sequence is the recommended end-to-end demonstration path:

```
1. Log in as Employee
   → Open IT Support chat
   → Type "My VPN is not connecting"
   → Watch the AI diagnose and guide through troubleshooting steps
   → Observe the ServiceNow incident created automatically

2. Log in as Employee (new session)
   → Type "I need to install VS Code"
   → Watch the AI detect a privileged request
   → Observe ticket created with status: WAITING_MANAGER

3. Log in as Manager
   → Open Manager Portal → Pending Approvals
   → Inspect the VS Code request
   → Click Approve, add approval notes

4. Log in as Admin
   → Open ITSM Queue → ticket is now READY_FOR_ADMIN
   → Click "Grant Temporary Admin Access"
   → Observe the Enterprise Admin Access Card (mock credentials, 15-min timer)

5. Switch back to Employee
   → Observe the Admin Access Card in the chat view
   → Admin marks the ticket COMPLETED

6. Log in as Admin
   → Open Analytics dashboard
   → Review ticket volume, category breakdown, SLA compliance
```

> **Note on temporary admin credentials:** The Enterprise Admin Access Card is a demonstration mock. It generates a static set of temporary credentials (`.\Administrator` / `Temp@4821#`) with a 15-minute countdown timer. This is intentionally simplified for the POC and is designed to be replaced by a real integration with **Windows LAPS**, **CyberArk PAM**, or **Azure Privileged Identity Management (PIM)** in a production deployment.

---

## 💡 Solution Overview

This project demonstrates how an AI agent can be embedded into an IT support workflow to handle first-line diagnosis, automatic ticket creation, and a structured approval process — all within a single, coherent application. It is not a production system; it is a well-structured proof of concept that demonstrates the full integration across AI, ITSM, and a React portal.

Key capabilities:

- Resolves common IT issues through a guided multi-node troubleshooting pipeline.
- Classifies and creates ServiceNow incidents with live-validated field mappings.
- Routes privileged software requests through a **Manager → Admin dual-approval workflow**.
- Monitors SLA compliance and escalates through three severity levels automatically.

---

## ✨ Key Features

| Capability | Details |
|---|---|
| **Agentic AI Troubleshooting** | 18-node LangGraph pipeline: Router → Intent → Diagnostics → Planner → Knowledge → Tool → Root Cause → Reflection → Decision |
| **AI Classification** | Gemini/Claude-powered ITSM classification with Pydantic validation, confidence thresholds (HIGH ≥ 0.90), and deterministic fallback rules |
| **Live ServiceNow Integration** | OAuth2 + Basic Auth incident creation with field mapping, TTL-cached metadata, and `sys_id` choice resolution |
| **Dual-Approval Workflow** | Manager approval → Admin grant → mock temporary credential delivery for privileged software installs |
| **RBAC** | Four roles: `EMPLOYEE`, `MANAGER`, `ADMIN`, `SUPERADMIN` — JWT HS256 secured |
| **SLA Engine** | APScheduler-driven monitoring (60s interval) with `WARNING_75`, `WARNING_90`, `BREACHED`, `ESCALATED_L1/L2/L3` states |
| **Prompt Injection Guard** | Three-tier risk classifier (HIGH/MEDIUM/LOW) screens messages before they enter the AI pipeline |
| **Rate Limiting** | Per-IP sliding-window limiter for `/chat`, `/auth/login`, and `/upload` — no external dependencies |
| **Immutable Audit Log** | Append-only RBAC audit trail with `correlation_id`, user, role, action, and ISO timestamps |
| **Analytics Dashboard** | Ticket volume by category and team, priority breakdown, SLA compliance trend (Recharts) |
| **Knowledge Base** | Admin-managed articles with AI-generated suggestions |
| **ServiceNow Metadata Validator** | Validates every configured ITSM field (category, subcategory, assignment group, etc.) against the live instance before incident creation |
| **Auto Schema Migration** | Missing database columns added automatically on startup — no manual migration needed |

---

## 🖥️ System Requirements

### Development (local)

| Requirement | Version |
|---|---|
| Python | 3.12+ |
| Node.js | 20+ |
| npm | 9+ |
| Git | Any recent version |
| OS | Windows 10/11, macOS, or Linux |

### External Services Required

| Service | Purpose | Notes |
|---|---|---|
| Google Gemini API | Primary AI provider | Free tier supported |
| Anthropic Claude API | Fallback AI provider | Optional |
| ServiceNow instance | Incident creation and metadata | Developer instance at developer.servicenow.com |

### Database

- **Development:** SQLite (included, no setup required)
- **Production:** PostgreSQL 14+

---

## 🏗️ System Architecture

```mermaid
graph TB
    subgraph FE["Frontend — Next.js 16 / React 19"]
        E[Employee Chat]
        M[Manager Portal]
        A[IT Admin Queue]
        AN[Analytics Dashboard]
        KB[Knowledge Base]
    end

    subgraph BE["Backend — FastAPI / Python 3.12"]
        API[FastAPI REST API]
        PG[PromptGuard]
        RL[Rate Limiter]
        SEC[Security Middleware]
        CS[ConversationService]
        LG[LangGraph Pipeline]
        CLS[ClassificationService]
        TO[TicketOrchestrator]
        SLA[SLA Escalation Engine]
        IES[IncidentEnrichmentService]
        FMS[FieldMappingService]
    end

    subgraph INT["Integrations"]
        SN[ServiceNow OAuth2 + REST]
        MG[Microsoft Graph - Mock]
        AD[Active Directory - Mock]
        VPN[VPN Adapter]
    end

    subgraph DATA["Data Layer"]
        DB[(SQLite / PostgreSQL)]
        CACHE[ServiceNow Metadata Cache]
    end

    E & M & A & AN & KB --> API
    API --> PG --> RL --> SEC --> CS
    CS --> LG & CLS & TO
    TO --> IES --> FMS --> SN
    TO --> DB
    SLA --> DB
    SN <--> CACHE
```

---

## 🤖 AI Workflow — LangGraph Pipeline

```mermaid
flowchart TD
    START([User Message]) --> Router{Router Node}

    Router -->|CHAT| Conv[Conversation Node]
    Router -->|TROUBLESHOOT| Memory[Memory Node]
    Conv --> END1([END])

    Memory --> CtxRouter{Context Router}
    CtxRouter -->|ticket_lifecycle| TL[Ticket Lifecycle Node]
    CtxRouter -->|ticket_status| TS[Ticket Status Node]
    CtxRouter -->|service_request| SR[Service Request Node]
    CtxRouter -->|intent| Intent[Intent Node]
    TS & SR --> END2([END])

    Intent --> DiagInt[Diagnostic Interview Node]
    DiagInt -->|questions asked| END3([END])
    DiagInt -->|ready| Planner[Planner Node]

    Planner --> Knowledge[Knowledge Node]
    Knowledge --> Tool[Tool Node]
    Tool --> MultiStep[Multi-Step Node]
    MultiStep -->|more tools needed| Tool
    MultiStep -->|complete| RootCause[Root Cause Node]

    RootCause --> Reflection[Reflection Node]
    Reflection --> Decision[Decision Node]

    Decision -->|CREATE_TICKET| Ticket[Ticket Node]
    Decision -->|EXECUTE_ACTION| Approval{Approval Gate}
    Decision -->|ASK_MORE_INFO| END4([END])

    Approval -->|APPROVED| Action[Action Node]
    Approval -->|PENDING / REJECTED| END5([END])

    Ticket --> TL
    TL -->|ticket created| Assignment[Assignment Node]
    TL -->|standalone lifecycle| Notification[Notification Node]
    Assignment --> Notification
    Action --> Notification
    Notification --> SLANode[SLA Node]
    SLANode --> END6([END])
```

---

## 🔄 Privileged Software Installation Workflow

```mermaid
sequenceDiagram
    participant E as Employee
    participant AI as AI Agent
    participant SN as ServiceNow
    participant DB as Database
    participant M as Manager Portal
    participant A as IT Admin Queue

    E->>AI: "Install VS Code"
    AI->>AI: Classify as SOFTWARE_INSTALLATION (privileged)
    AI->>SN: Create Incident via OAuth2
    SN-->>AI: INC number + sys_id returned
    AI->>DB: Persist ticket (status=WAITING_MANAGER)
    AI-->>E: "Request raised. Awaiting manager approval."

    M->>DB: View pending approvals
    M->>DB: Approve (approved_by, approval_notes, approved_at)
    DB-->>A: Ticket status → READY_FOR_ADMIN

    A->>DB: Grant temporary admin access (status=ACCESS_GRANTED)
    DB-->>E: Admin Access Card shown in chat (mock credentials, 15-min timer)

    E->>AI: "Installation complete"
    A->>DB: Mark ticket COMPLETED
```

---

## 🧰 Tech Stack

### Backend

| Component | Technology |
|---|---|
| Runtime | Python 3.12 |
| API Framework | FastAPI 0.115 + Uvicorn |
| AI Orchestration | LangGraph StateGraph (18 nodes) |
| AI Providers | Google Gemini (primary), Anthropic Claude (fallback) |
| ORM | SQLAlchemy 2.x |
| Database | SQLite (dev) / PostgreSQL (production) |
| Authentication | JWT HS256 via `python-jose` |
| Scheduling | APScheduler (SLA monitor, 60s interval) |
| HTTP Client | httpx |
| Validation | Pydantic v2 |
| Logging | Structured JSON with per-request correlation IDs |

### Frontend

| Component | Technology |
|---|---|
| Framework | Next.js 16.2 / React 19 |
| Language | TypeScript 5 |
| Styling | Tailwind CSS 4 |
| Animations | Framer Motion 12 |
| Charts | Recharts 3 |
| Icons | Lucide React |

---

## 📁 Folder Structure

```
bridgestone-it-agent/
├── backend/
│   ├── app/
│   │   ├── adapters/              # ServiceNow, MS Graph, AD, VPN adapters
│   │   ├── api/                   # Auth & Analytics REST routers
│   │   ├── core/                  # Security middleware, rate limiter, tracing, JSON logger
│   │   ├── database/
│   │   │   ├── models/            # 19 SQLAlchemy ORM models
│   │   │   ├── repositories/      # Repository pattern DAOs
│   │   │   ├── connection.py      # Engine + automatic startup schema migration
│   │   │   └── session.py
│   │   ├── graph/                 # LangGraph workflow
│   │   │   ├── graph.py           # Compiled StateGraph (18 nodes)
│   │   │   ├── state.py           # AgentState TypedDict
│   │   │   └── nodes/             # Individual graph node implementations
│   │   ├── services/              # 69 service modules
│   │   │   ├── ai_provider.py
│   │   │   ├── classification_service.py
│   │   │   ├── conversation_service.py
│   │   │   ├── field_mapping_service.py
│   │   │   ├── incident_enrichment_service.py
│   │   │   ├── prompt_guard.py
│   │   │   ├── servicenow_client.py
│   │   │   ├── servicenow_metadata_cache.py
│   │   │   ├── servicenow_metadata_validator.py
│   │   │   ├── sla_escalation_service.py
│   │   │   ├── ticket_orchestrator.py
│   │   │   └── ticket_service.py
│   │   └── main.py                # FastAPI application entry point
│   ├── tests/
│   ├── knowledge_base/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/                   # Next.js App Router pages
│       └── components/
│           ├── SupportChatView.tsx
│           ├── ITSMQueueView.tsx
│           ├── ManagerPortal.tsx
│           ├── AnalyticsView.tsx
│           ├── KnowledgeBase.tsx
│           └── shared/
│               └── EnterpriseAdminAccessCard.tsx
├── docs/                          # Architecture and integration documentation
├── infrastructure/                # Docker Compose configurations
├── .env
└── README.md
```

---

## ⚙️ Installation Guide

### Prerequisites

- Python 3.12+
- Node.js 20+
- Git
- A [ServiceNow developer instance](https://developer.servicenow.com)
- A Google Gemini API key

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/bridgestone-it-agent.git
cd bridgestone-it-agent
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv_312
.\venv_312\Scripts\activate          # Windows
# source venv_312/bin/activate        # macOS / Linux

pip install -r requirements.txt

# Create and configure environment file
cp ../.env.example .env
# Edit .env with your API keys and ServiceNow credentials
```

### 3. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local: NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

---

## 🔑 Environment Variables

```env
# ── AI Providers ──────────────────────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key      # Optional; used as fallback

# ── ServiceNow ────────────────────────────────────────────────────────────────
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=api_user
SERVICENOW_PASSWORD=api_password
SERVICENOW_CLIENT_ID=oauth_client_id
SERVICENOW_CLIENT_SECRET=oauth_client_secret
SERVICENOW_USE_MOCK=false                     # Set to true to disable live calls

# ── Authentication ────────────────────────────────────────────────────────────
JWT_SECRET_KEY=your_jwt_secret_min_32_chars
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=480

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=sqlite:///./bridgestone_it_agent.db
# DATABASE_URL=postgresql://user:password@localhost:5432/bridgestone_db

# ── Rate Limiting ─────────────────────────────────────────────────────────────
RATE_LIMIT_CHAT=30
RATE_LIMIT_CHAT_WINDOW=60
RATE_LIMIT_LOGIN=10
RATE_LIMIT_LOGIN_WINDOW=60

# ── Security Headers ──────────────────────────────────────────────────────────
HSTS_ENABLED=false          # Set to true in production (HTTPS only)
MAX_REQUEST_SIZE_KB=512
```

---

## 🚀 Running the Application

### Start the Backend

```bash
cd backend
.\venv_312\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API: `http://127.0.0.1:8000`
- Interactive API docs (Swagger UI): `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

### Start the Frontend

```bash
cd frontend
npm run dev
```

- UI: `http://localhost:3000`

---

## 📡 API Documentation

Full interactive documentation is available at `http://127.0.0.1:8000/docs` when the backend is running.

### Authentication

| Method | Endpoint | Access |
|---|---|---|
| `POST` | `/auth/login` | Public |
| `GET` | `/auth/me` | Authenticated |

### Chat & Tickets

| Method | Endpoint | Access |
|---|---|---|
| `POST` | `/chat` | EMPLOYEE |
| `GET` | `/tickets` | ADMIN / MANAGER |
| `GET` | `/tickets/{id}` | ADMIN / MANAGER |
| `PUT` | `/tickets/{id}/status` | ADMIN |
| `GET` | `/my-tickets` | EMPLOYEE |

### Manager Workflow

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/manager/tickets` | MANAGER / ADMIN |
| `POST` | `/manager/tickets/{id}/approve` | MANAGER |
| `POST` | `/manager/tickets/{id}/reject` | MANAGER |

### Admin Operations

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/admin/queue` | ADMIN |
| `POST` | `/admin/tickets/{id}/grant-access` | ADMIN |
| `POST` | `/admin/tickets/{id}/complete` | ADMIN |

### Analytics & Health

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/api/analytics/overview` | ADMIN |
| `GET` | `/api/analytics/sla` | ADMIN |
| `GET` | `/health` | Public |
| `GET` | `/system-status` | ADMIN |

### ServiceNow

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/servicenow/validate` | ADMIN |
| `POST` | `/servicenow/incidents` | ADMIN |

---

## 🔒 Security Features

### Authentication & Authorisation
- **JWT (HS256)** tokens with configurable expiry, issued by the `/auth/login` endpoint.
- **Role-Based Access Control**: `EMPLOYEE`, `MANAGER`, `ADMIN`, `SUPERADMIN`.
- All non-public endpoints protected by `RoleChecker` FastAPI dependencies.

### API Layer Security
- **Security Headers Middleware**: Injects `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, configurable HSTS, and Content-Security-Policy on every response.
- **Request Size Limiting**: HTTP 413 returned before the request body is read if the payload exceeds `MAX_REQUEST_SIZE_KB`.
- **Sliding-Window Rate Limiting**: Per-IP limits for `/chat`, `/auth/login`, and `/upload`; implemented in-process with no external dependencies.
- **CORS**: Allowlist-based origin enforcement.

### AI Safety
- **Prompt Injection Guard** (`prompt_guard.py`): Three-tier classifier runs before every LLM call.
  - `HIGH` confidence attack → HTTP 400 returned, entry written to the immutable audit log.
  - `MEDIUM` confidence → suspicious fragment removed, pipeline continues with sanitised input.
  - `LOW` confidence → request allowed through with a structured warning log entry.

### Audit & Observability
- **RBAC Audit Log**: Append-only entries recording `correlation_id`, `user`, `role`, `action`, `ticket_id`, and ISO timestamps.
- **Structured JSON Logging**: Every request tagged with `request_id`, `correlation_id`, `session_id`, `user`, `role`, `endpoint`, `execution_time`, and `status_code`.

---

## 📊 Logging & Monitoring

### Log Format

Every log entry is a JSON object for easy ingestion by log aggregators (e.g. Datadog, Elastic):

```json
{
  "timestamp": "2026-07-26T06:12:06.643094Z",
  "level": "INFO",
  "logger": "it-agent-backend",
  "message": "FastAPI Endpoint GET '/tickets': Fetching tickets",
  "request_id": "req-bdd7b27d",
  "correlation_id": "corr-cfe260ca",
  "user": "admin",
  "role": "ADMIN",
  "endpoint": "/tickets",
  "execution_time": 0.041,
  "status_code": 200
}
```

### SLA State Machine

```mermaid
stateDiagram-v2
    [*] --> HEALTHY
    HEALTHY --> WARNING_75 : 75% of SLA elapsed
    WARNING_75 --> WARNING_90 : 90% of SLA elapsed
    WARNING_90 --> BREACHED : SLA deadline passed
    BREACHED --> ESCALATED_L1 : immediately on breach
    ESCALATED_L1 --> ESCALATED_L2 : breach + 30 min
    ESCALATED_L2 --> ESCALATED_L3 : breach + 60 min
```

| State | Notified Parties |
|---|---|
| `WARNING_75` | Assigned team, Manager |
| `WARNING_90` | Assigned team, Manager, Admin |
| `BREACHED` | All — `SlaEscalationHistory` record created |
| `ESCALATED_L2 / L3` | All — additional escalation history entries |

---

## 🔗 ServiceNow Integration

### Incident Creation Pipeline

```mermaid
flowchart LR
    A[User Message] --> B["ClassificationService\n(Gemini AI)"]
    B --> C["IncidentEnrichmentService\n(metadata resolution)"]
    C --> D["FieldMappingService\n(SN field builder)"]
    D --> E["ServiceNowMetadataValidator\n(live instance validation)"]
    E --> F["ServiceNowClient\n(OAuth2 REST call)"]
    F --> G[(ServiceNow Instance)]
    G --> H[INC number returned]
    H --> I[Persisted in DB + notification sent]
```

### Authentication
Supports **OAuth 2.0 Client Credentials** (primary) with automatic **Basic Auth** fallback.

### Metadata Validation
- **TTL-based cache**: Valid choices for categories, subcategories, assignment groups, contact types, and priority/urgency/impact are fetched from the live ServiceNow instance and cached with a configurable TTL.
- **`ServiceNowMetadataValidator`**: Before every incident is submitted, all configured field values are checked against the cache. A full validation report is available at `GET /servicenow/validate`.
- **`ServiceNowChoiceResolver`**: Resolves human-readable labels (e.g. `"IT Support"`) to the internal `sys_id` values that the ServiceNow REST API requires.

### Field Mapping

| Field | How It Is Resolved |
|---|---|
| `contact_type` | Fixed to `virtual_agent` for AI-sourced requests |
| `u_type` | Mapped from issue category |
| `category` / `subcategory` | Validated against cached ServiceNow metadata |
| `assignment_group` | Resolved to `sys_id` via `ServiceNowChoiceResolver` |
| `urgency` / `impact` / `priority` | Calculated by `SlaService` based on category and config — not set by AI |

---

## 📸 Screenshots

### Login Page
![Login page with Employee, Manager, and Admin quick-access profiles](image.png)

### IT Support Chat (Employee View)
![AI-powered IT Support Assistant with example issue prompts](image-1.png)

### Home Dashboard
![Home view with IT Support and IT Actions tiles, and recent tickets list](image-2.png)

### Manager Portal — Pending Approvals
![Manager portal showing pending service request approvals table](image-3.png)

### IT Admin Console — ITSM Queue Dashboard
![Admin console showing ticket KPIs, tickets by category, and priority breakdown](image-4.png)

### Analytics — SLA Compliance and Volume Trend
![Analytics view showing SLA compliance rate and weekly ticket volume trend](image-5.png)

---

## 🔮 Future Improvements

Items listed here are intentionally not implemented in this POC and are documented as the natural next steps for a production deployment:

| Area | Planned Enhancement |
|---|---|
| **Windows LAPS / CyberArk PAM** | Replace mock temporary credentials with a real privileged access management integration |
| **Azure PIM** | Integrate Azure Privileged Identity Management for just-in-time admin access |
| **MS Teams Approvals** | Native Microsoft Teams Adaptive Card approval flows for manager decisions |
| **ServiceNow Approval Engine** | Use native ServiceNow approval workflows rather than a local state machine |
| **Redis Rate Limiting** | Replace the in-process sliding-window limiter with a Redis-backed distributed implementation for multi-process deployments |
| **WebSocket Notifications** | Real-time push notifications to replace client-side polling |
| **Azure Entra ID Sync** | Live user sync for automatic manager resolution and user lookup |
| **pgvector RAG** | Full vector-embedding semantic search over the knowledge base |
| **Prometheus / Grafana** | Metrics export and production observability dashboards |
| **Kubernetes / Helm** | Production-grade container deployment |

---

## 👥 Contributors

| Name | Responsibilities |
|---|---|
| **Raghvendra Bhati** | Full-stack development — system architecture, LangGraph AI pipeline, ServiceNow OAuth2 integration, ITSM classification service, SLA escalation engine, dual-approval workflow, RBAC, prompt injection guard, structured logging, Next.js portals (Employee Chat, Manager Portal, IT Admin Queue, Analytics, Knowledge Base) |

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](./LICENSE) file for full terms.

---

<div align="center">

Built as a portfolio proof-of-concept. Powered by **Gemini AI** · **LangGraph** · **ServiceNow** · **Next.js**.

</div>
