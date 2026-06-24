# Bridgestone IT Support Agent - Deployment Guide

This guide provides instructions for containerizing, configuring, and deploying the Bridgestone IT support platform in development, QA, and production environments.

---

## 1. System Architecture

Below is the deployment architecture for the containerized application.

```mermaid
graph TD
    %% Roles
    User([Employee / Manager / Admin])

    %% Proxy Layer
    subgraph Proxy ["Edge Routing (NGINX)"]
        Nginx[nginx:stable-alpine]
    end

    %% Application Layer
    subgraph App ["Container Network (bridgestone-network)"]
        Frontend[node:24-alpine]
        Backend[python:3.11-slim]
        Postgres[postgres:15-alpine]
        Redis[redis:7-alpine]
    end

    %% External Systems
    subgraph External ["External Services"]
        Gemini[Google Gemini AI API]
        ServiceNow[ServiceNow Enterprise Instance]
        Graph[Microsoft Graph API]
        AD[Active Directory Server]
        VPN[VPN Gateway]
    end

    %% Data Volumes
    subgraph Volumes ["Persistent Storage"]
        PG_Vol[(postgres_data_prod)]
        RD_Vol[(redis_data_prod)]
    end

    %% Connections
    User -->|Port 80/443| Nginx
    Nginx -->|/| Frontend
    Nginx -->|/api| Backend
    
    Frontend -->|Relative fetch| Nginx
    Backend -->|SQL Query| Postgres
    Backend -->|Cache Query| Redis

    Postgres -->|Mount| PG_Vol
    Redis -->|Mount| RD_Vol

    Backend -->|Model Queries| Gemini
    Backend -->|Sync Incidents| ServiceNow
    Backend -->|Verify Profile| Graph
    Backend -->|Check Status| AD
    Backend -->|Check Gateway| VPN
```

### Container Startup & Healthcheck Orchestration

The platform relies on healthcheck-based dependency chains to guarantee zero-downtime startups and avoid connection failures.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Postgres_Check : Start Postgres
    Postgres_Check --> Redis_Check : pg_isready (HEALTHY)
    Redis_Check --> Backend_Check : redis-cli ping (HEALTHY)
    Backend_Check --> Frontend_Check : GET /health (HEALTHY)
    Frontend_Check --> Nginx_Proxy : wget HTTP 200 (HEALTHY)
    Nginx_Proxy --> [*] : NGINX matches endpoints (ONLINE)
```

1. **`postgres` & `redis`**: Start first and run internal health pings.
2. **`backend`**: Starts only after `postgres` and `redis` are `service_healthy`.
3. **`frontend`**: Starts only after `backend` is `service_healthy` (determined by `GET /health` responding).
4. **`nginx`**: Starts last and binds external port `80` to proxy request traffic.

---

## 2. Environment Configurations

All variables are managed via files in `infrastructure/env/`:
* **`dev.env`**: Configured for local development with default SQLite fallbacks or dev databases.
* **`qa.env`**: Target for test execution and QA environments.
* **`prod.env`**: Strict configuration for live production environments.

### Environment Variable Catalog

| Variable | Description | Example (Production) |
| :--- | :--- | :--- |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection URL. | `postgresql://prod_admin:securepass@postgres:5432/bridgestone_it_agent` |
| `REDIS_URL` | Connection URL for Redis instances. | `redis://redis:6379/0` |
| `JWT_SECRET` | Secret key used to sign access/refresh tokens. | *Keep randomly generated and unique to env* |
| `GEMINI_API_KEY` | Gemini LLM integration API Key. | `AQ.Ab8RN6...` |
| `SERVICENOW_URL` | Endpoint for ServiceNow instance. | `https://bridgestone.service-now.com/` |
| `SERVICENOW_USERNAME` | Integration Username. | `prod_servicenow_api_user` |
| `SERVICENOW_PASSWORD` | Integration Password. | `prod_highly_secure_password` |

---

## 3. Docker Compose Deployment

Commands are executed from the workspace root or the `infrastructure/compose/` directory.

### A. Development Deployment
Includes bind-mount volumes to allow code hot-reloading. Ports `8000`, `3000`, `5432`, and `6379` are exposed to the host machine for debugging.
```bash
# Navigate to compose directory
cd infrastructure/compose

# Spin up Dev Environment
docker compose -f docker-compose.dev.yml up --build -d
```

### B. QA Deployment
Packages code directly inside the Docker images without local filesystem mounting to guarantee environment immutability.
```bash
cd infrastructure/compose

# Spin up QA Environment
docker compose -f docker-compose.qa.yml up --build -d
```

### C. Production Deployment (Enterprise Architecture)
Locks down all internal container ports. Binds **only** the NGINX reverse proxy port `80` to the host.
```bash
cd infrastructure/compose

# Spin up Production Environment
docker compose -f docker-compose.prod.yml up --build -d
```
Once deployed, the app will be accessible at:
* **Frontend UI**: `http://localhost/`
* **Backend API**: `http://localhost/api` (e.g. `http://localhost/api/health` checking health).

---

## 4. Kubernetes Migration Roadmap

The Docker-based infrastructure is structured to support seamless migration to orchestration platforms like **Azure Kubernetes Service (AKS)**, **AWS EKS**, or on-prem Kubernetes configurations.

### 1. Secret Management
* Transition `.env` files into native **Kubernetes Secrets** or sync with Enterprise vaults (e.g., Azure Key Vault, HashiCorp Vault) using a Secret Provider class.

### 2. Manifest Mappings (Deployments & Services)
* **PostgreSQL / Redis**: Migrate to managed cloud instances (e.g., Azure Database for PostgreSQL, AWS ElastiCache) rather than deploying them inside Kubernetes to improve scalability and backup reliability.
* **Backend & Frontend**: Create `Deployment` manifests with specific cpu/memory request limits and resource autoscaling (HPA) policies.
* **NGINX**: Replace Nginx container with a **Kubernetes Ingress Controller** (e.g., NGINX Ingress Controller) linking directly to routing routes.

### 3. Readiness and Liveness Probes
Use the container health checks defined in this guide directly in the Kubernetes Deployment specs:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

---

## 5. Troubleshooting & Logs

### View Container Logs
```bash
# General compose logs
docker compose -f docker-compose.prod.yml logs -f

# Check Backend logs
docker logs bridgestone-backend-prod -f
```

### Reset Database Volumes
If database migrations or schema corruption occur, reset the persistent volumes:
```bash
docker compose -f docker-compose.prod.yml down -v
```
