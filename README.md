# Bridgestone IT Support Agent (Enterprise Edition)

The Bridgestone IT Support Agent is a production-grade, feature-complete POC platform integrating an advanced LangGraph Multi-Agent network, dynamic multi-step troubleshooting, context-grounded RAG, ServiceNow sync adapters, Microsoft Graph/Entra ID integrations, and strict role-based access control (RBAC).

---

## 1. System Architecture

The platform uses a containerized multi-tier service network managed via Docker Compose or Kubernetes manifests.

### Deployment Layout

* **Edge Routing (Reverse Proxy):** NGINX maps paths to frontend/backend services.
* **Frontend UI Application:** Next.js / React application rendering high-fidelity interactive dashboard pages.
* **Backend API Engine:** FastAPI (Python 3.12) running LangGraph state machines.
* **Storage Layer:** PostgreSQL for persistent transaction records (audit trails, ticket transitions) and Redis for high-speed cache management.

### LangGraph Network Pipeline

```
Router ──> Conversation Node (Chitchat) ────> END
       └──> Memory Node ──> Context Router ──>
            ├──> Ticket Status Node ────────> END
            ├──> Service Request Node ──────> END
            └──> Troubleshooting Nodes (Intent ──> Diagnostic Interview ──> Planner ──> Tool Execution ──> Multi-Step Loop ──> Root Cause ──> Reflection ──> Decision Node ──> Approval Node ──> Action Node ──> Notification/SLA ──> END)
```

---

## 2. Directory Structure

```
bridgestone-it-agent/
├── backend/                  # Python FastAPI application
│   ├── app/                  # Main source package
│   │   ├── agents/           # Specialized LLM agents (conversation, planner, reflection)
│   │   ├── core/             # Authentication, security rules, prometheus metrics
│   │   ├── database/         # Models, connection pool configurations, migrations
│   │   ├── graph/            # LangGraph pipeline state definitions & node routers
│   │   └── services/         # Business services (SLA, approvals, catalog, active directory)
│   ├── mock_gemini.py        # Gemini client override for deterministic offline testing
│   ├── verify_production_readiness.py  # Production readiness validation script
│   └── verify_enterprise_suite.py       # Master QA validation runner
├── docs/                     # Architectural design guides and configuration specifications
├── frontend/                 # React Next.js user interface application
└── infrastructure/           # Container configurations, deployment compose files, env files
```

---

## 3. Production Readiness Checks

Before releasing the platform to staging or production, run the automated compliance auditor:

```bash
# Execute the compliance checker
python backend/verify_production_readiness.py
```

### Audits Performed:
* **Secrets Scan:** Scans the active codebase directory (`backend/app/`) for potential credential leaks or hardcoded API keys.
* **SQL Injection Scan:** Audits SQL queries to confirm all parameters are securely bound rather than interpolated as raw strings.
* **Connection Pooling:** Verifies that connection limits (`pool_size=20`, `max_overflow=10`, `pool_timeout=30`, `pool_recycle=1800`) are active for production engines.
* **SQLite Optimization:** Checks that WAL journal mode and NORMAL synchronicity are enabled if SQLite fallback is triggered in lower environments.
* **CORS Restrictions:** Identifies wildcard CORS configurations (`allow_origins=["*"]`) and warns deployers to use origin allowlists in production.
* **Global Error Middleware:** Assures the presence of custom global error middleware in the web endpoints.

---

## 4. Quick Start: Local Deployment

Ensure Docker is installed and running on your host machine.

### A. Development Build
Includes local filesystem bind-mounts and hot-reloading:
```bash
cd infrastructure/compose
docker compose -f docker-compose.dev.yml up --build -d
```

### B. Production Build
Locks down container endpoints, building immutable containers and reverse proxying through NGINX on port `80`:
```bash
cd infrastructure/compose
docker compose -f docker-compose.prod.yml up --build -d
```
The application will be serving at `http://localhost/` for users and `http://localhost/api/` for endpoints.

---

## 5. Operations & Logs

View container runtime logs using Docker CLI:
```bash
# Stream production backend logs
docker logs bridgestone-backend-prod -f
```

For full environment guides, database migration manuals, security protocols, and operational workflows, refer to the documentation catalog located in the `/docs` directory.
