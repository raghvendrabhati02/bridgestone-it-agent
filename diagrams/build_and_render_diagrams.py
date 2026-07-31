import os
import subprocess
import json

DIAGRAMS_DIR = r"C:\Projects\bridgestone-it-agent\diagrams"

CONFIG_JSON = {
    "theme": "dark",
    "themeVariables": {
        "darkMode": True,
        "background": "#0b0f19",
        "primaryColor": "#1e293b",
        "primaryTextColor": "#f8fafc",
        "primaryBorderColor": "#38bdf8",
        "lineColor": "#38bdf8",
        "secondaryColor": "#0f172a",
        "tertiaryColor": "#1e1e2e",
        "fontFamily": "Segoe UI, Calibri, sans-serif",
        "fontSize": "13px",
        "nodeBorder": "#38bdf8",
        "clusterBkg": "#0f172a",
        "clusterBorder": "#334155",
        "titleColor": "#f8fafc",
        "edgeLabelBackground": "#0f172a"
    }
}

config_path = os.path.join(DIAGRAMS_DIR, "mermaid_config.json")
with open(config_path, "w", encoding="utf-8") as f:
    json.dump(CONFIG_JSON, f, indent=2)

DIAGRAMS = {
    "fig_8_1_issue_resolution.mmd": """sequenceDiagram
    autonumber
    actor Employee as Employee (Browser)
    participant Gateway as API Gateway (FastAPI)
    participant MW as Middleware & Security
    participant Guard as PromptGuard Classifier
    participant Graph as LangGraph Engine
    participant Tools as Enterprise Diagnostics
    participant SN as ServiceNow API

    Employee->>Gateway: POST /chat (User Message + JWT)
    Gateway->>MW: Rate Limiter & JWT Role Assertion
    MW-->>Gateway: Authorized (EMPLOYEE role)
    Gateway->>Guard: Scan prompt for injection risks
    Guard-->>Gateway: Prompt Risk: LOW / PASS
    Gateway->>Graph: StateGraph.invoke(AgentState)
    
    rect rgb(15, 23, 42)
        Note over Graph: Agentic Diagnostic Cycle
        Graph->>Graph: Router -> Memory -> Intent Node
        Graph->>Tools: Execute Diagnostic Tools (VPN / AD / Network)
        Tools-->>Graph: Tool Results & System Status
        Graph->>Graph: Multi-Step Node -> Root Cause -> Reflection
    end

    alt Self-Service Resolution Identified
        Graph-->>Employee: Return Guided Resolution Response
    else Escalation Required (Create Ticket)
        Graph->>SN: OAuth2 Incident Creation (Category, CI, Priority)
        SN-->>Graph: Incident Number (e.g. INC0071633)
        Graph-->>Employee: Return INC Number & SLA SLA Commitment
    end
""",

    "fig_8_2_approval_workflow.mmd": """sequenceDiagram
    autonumber
    actor Employee as Employee
    participant Agent as AI Assistant
    participant DB as Platform DB
    actor Manager as Line Manager
    actor Admin as IT Administrator
    participant SN as ServiceNow

    Employee->>Agent: Request Privileged Software (e.g., VS Code)
    Agent->>SN: Create Incident (Category: SOFTWARE_INSTALLATION)
    SN-->>Agent: Incident INC0071640 Created
    Agent->>DB: Persist Ticket (Status: WAITING_MANAGER)
    Agent-->>Employee: Request Logged — Pending Manager Approval

    rect rgb(15, 23, 42)
        Note over Manager, DB: Step 1: Manager Approval Phase
        Manager->>DB: Approve Request via Manager Portal
        DB->>DB: Update Status -> READY_FOR_ADMIN
    end

    rect rgb(15, 23, 42)
        Note over Admin, DB: Step 2: IT Admin Access Grant Phase
        Admin->>DB: Provision Access (LAPS Temporary Credential)
        DB->>DB: Update Status -> ACCESS_GRANTED (15-min TTL)
        Admin->>Employee: Deliver Temporary Credentials Card
    end

    Admin->>DB: Mark Ticket COMPLETED
    DB->>SN: Update ServiceNow Incident Status -> RESOLVED
""",

    "fig_8_3_sla_state_machine.mmd": """stateDiagram-v2
    [*] --> HEALTHY: Ticket Created (SLA Timer Starts)
    
    HEALTHY --> WARNING_75: SLA 75% Elapsed
    WARNING_75 --> WARNING_90: SLA 90% Elapsed
    WARNING_90 --> BREACHED: SLA 100% Elapsed
    
    state BREACHED {
        [*] --> ESCALATED_LEVEL_1: Immediate Breach Notification
        ESCALATED_LEVEL_1 --> ESCALATED_LEVEL_2: Breach + 30 Mins
        ESCALATED_LEVEL_2 --> ESCALATED_LEVEL_3: Breach + 60 Mins
    }

    HEALTHY --> RESOLVED: Issue Resolved
    WARNING_75 --> RESOLVED: Issue Resolved
    WARNING_90 --> RESOLVED: Issue Resolved
    BREACHED --> RESOLVED: Issue Resolved
    
    RESOLVED --> [*]
""",

    "fig_9_1_high_level_arch.mmd": """flowchart TB
    subgraph ClientLayer["1. Client Layer (Portal Surfaces)"]
        FE1["Employee Chat Portal"]
        FE2["Manager Approval Portal"]
        FE3["IT Admin Queue"]
        FE4["Analytics & KB Dashboard"]
    end

    subgraph IngressLayer["2. Ingress & Reverse Proxy"]
        NGINX["Nginx Ingress Proxy\n(TLS Termination / Route Dispatcher)"]
    end

    subgraph GatewayLayer["3. API Gateway Tier (FastAPI)"]
        MW1["Rate Limiter\n(Sliding Window)"]
        MW2["PromptGuard\n(Injection Classifier)"]
        MW3["JWT & RBAC\nAuth Middleware"]
        MW4["Security Headers\n& Payload Validation"]
    end

    subgraph OrchestrationLayer["4. AI Agentic Orchestration Tier (LangGraph)"]
        LG1["AgentState Graph\n(23 Conditional Nodes)"]
        LG2["Gemini 2.5 Flash\n(Primary LLM)"]
        LG3["Claude 3 Sonnet\n(Fallback LLM)"]
    end

    subgraph ServiceLayer["5. Deterministic Business Logic Tier"]
        SVC1["Classification Service"]
        SVC2["Incident Enrichment"]
        SVC3["Field Mapping Service"]
        SVC4["SLA Escalation Engine"]
        SVC5["Immutable Audit Logger"]
    end

    subgraph IntegrationLayer["6. Enterprise System Adapters"]
        AD1["ServiceNow Adapter\n(OAuth2 / REST API)"]
        AD2["MS Graph / AD Adapter"]
        AD3["VPN Diagnostics Tool"]
    end

    subgraph DataLayer["7. Persistence & Caching Tier"]
        DB1[("PostgreSQL 14 / SQLite")]
        DB2[("Redis Cache\n(Metadata & Sessions)")]
    end

    ClientLayer --> NGINX
    NGINX --> GatewayLayer
    GatewayLayer --> OrchestrationLayer
    OrchestrationLayer --> ServiceLayer
    ServiceLayer --> IntegrationLayer
    ServiceLayer --> DataLayer
    IntegrationLayer --> DB1
""",

    "fig_10_1_ai_fallback.mmd": """flowchart LR
    subgraph Request["AI Request Stream"]
        REQ["Inbound Prompt"]
    end

    subgraph Abstraction["AI Abstraction Interface"]
        BASE["BaseAIProvider Contract"]
    end

    subgraph Tier1["Primary Provider"]
        GEMINI["Google Gemini 2.5 Flash\n(High Concurrency / Fast Function Calling)"]
    end

    subgraph Tier2["Secondary Fallback"]
        CLAUDE["Anthropic Claude 3 Sonnet\n(High-Reasoning Fallback)"]
    end

    subgraph Tier3["Deterministic Fallback"]
        RULE["Keyword Rules Classifier\n(11-Domain Regex Engine)"]
    end

    REQ --> BASE
    BASE -->|Primary Path| GEMINI
    GEMINI -->|Timeout / API Error / Rate Limit| CLAUDE
    CLAUDE -->|Provider Outage| RULE
    RULE -->|Guaranteed Output| Out["Validated Classification"]
    GEMINI -->|Success| Out
    CLAUDE -->|Success| Out
""",

    "fig_11_1_langgraph_workflow.mmd": """flowchart TB
    subgraph Entry["1. Ingress & Router"]
        START([User Input]) --> ROUTER{Router Node}
        ROUTER -->|CHAT| CONV[Conversation Node] --> END1([End Response])
        ROUTER -->|TROUBLESHOOT| MEMORY[Memory Node]
    end

    subgraph Dispatch["2. Context Dispatcher"]
        MEMORY --> CTX{Context Router}
        CTX -->|ticket_status| T_STAT[Ticket Status Node] --> END2([End Response])
        CTX -->|service_request| S_REQ[Service Request Node] --> END3([End Response])
        CTX -->|intent| INTENT[Intent Classification Node]
    end

    subgraph DiagnosticLoop["3. Diagnostic & Tool Execution Loop"]
        INTENT --> DIAG[Diagnostic Interview Node]
        DIAG -->|Questions Pending| END4([Await User Input])
        DIAG -->|Ready| PLANNER[Planner Node]
        PLANNER --> KB[Knowledge Node]
        KB --> TOOL[Tool Execution Node]
        TOOL --> MULTI{Multi-Step Node}
        MULTI -->|More Tools Needed| TOOL
        MULTI -->|Diagnostics Complete| ROOT[Root Cause Node]
    end

    subgraph DecisionTier["4. Synthesis & Governance"]
        ROOT --> REFLECT[Reflection Node]
        REFLECT --> DECIDE{Decision Node}
        DECIDE -->|ASK_MORE_INFO| END5([Ask User])
        DECIDE -->|EXECUTE_ACTION| APPROVAL{Approval Node}
        DECIDE -->|CREATE_TICKET| TICKET[Ticket Node]
    end

    subgraph Execution["5. Ticket Lifecycle & SLA"]
        APPROVAL -->|APPROVED| ACTION[Action Node] --> LIFECYCLE
        APPROVAL -->|REJECTED / PENDING| END6([Halt Action])
        TICKET --> LIFECYCLE[Ticket Lifecycle Node]
        LIFECYCLE --> ASSIGN[Assignment Node]
        ASSIGN --> NOTIF[Notification Node]
        NOTIF --> SLA[SLA Tracking Node] --> FINISH([Pipeline Complete])
    end
""",

    "fig_12_1_integration_topology.mmd": """flowchart LR
    subgraph CoreBackend["Bridgestone IT Platform Core"]
        BE["FastAPI App Engine"]
    end

    subgraph SNIntegration["ServiceNow Integration Subsystem"]
        SNC["ServiceNow Client\n(OAuth2 Token Manager)"]
        SNCache["ServiceNow Metadata Cache\n(TTL: 3600s)"]
        Val["Metadata Validator"]
        Map["Field Mapping Service"]
    end

    subgraph ExternalSystems["Enterprise Endpoint Services"]
        SN_API["ServiceNow Table API\n(REST HTTPS)"]
        MS_GRAPH["Microsoft Graph API\n(Azure AD / Entra)"]
        VPN_GW["GlobalProtect VPN Gateway\n(Diagnostic Probe)"]
    end

    BE --> SNC
    SNC --> SNCache
    SNCache --> Val
    Val --> Map
    SNC -->|OAuth2 Bearer| SN_API
    BE -->|REST / SDK| MS_GRAPH
    BE -->|ICMP / SNMP| VPN_GW
""",

    "fig_12_2_servicenow_validation.mmd": """flowchart TB
    A["Raw LLM Classification Output"] --> B["Field Mapping Service\n(Alias Normalization)"]
    B --> C{"Metadata Validator\n(Check Choice Values)"}
    
    C -->|Valid Metadata| D["Incident Enrichment Service\n(Impact / Urgency Rules)"]
    C -->|Invalid / Unknown Choice| E["Local Taxonomy Fallback\n(incident_config.json)"]
    E --> D

    D --> F["ServiceNow Client\n(Payload Assembly)"]
    F --> G["ServiceNow Table API\n(POST /api/now/table/incident)"]
    G --> H["Sys_ID & INC Number Returned"]
    H --> I["Persist to Local Platform DB\n(servicenow_id / servicenow_number)"]
""",

    "fig_13_1_security_stack.mmd": """flowchart TB
    subgraph L1["Layer 1: Network & Boundary Security"]
        N1["Nginx Ingress Proxy"]
        N2["HTTPS TLS 1.3 Termination"]
    end

    subgraph L2["Layer 2: Transport & HTTP Security Headers"]
        H1["HSTS (max-age=31536000)"]
        H2["Content Security Policy (CSP)"]
        H3["X-Frame-Options: DENY"]
        H4["X-Content-Type-Options: nosniff"]
    end

    subgraph L3["Layer 3: Application Guardrails"]
        A1["Request Size Limiter (512 KB)"]
        A2["Sliding-Window Rate Limiter"]
        A3["PromptGuard 3-Tier Classifier"]
        A4["JWT Auth & RoleChecker (RBAC)"]
    end

    subgraph L4["Layer 4: Compliance & Auditability"]
        D1["Immutable Audit Log (SHA-256 Hashes)"]
        D2["RBAC Denial Auditor"]
        D3["Security Event Logger"]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
""",

    "fig_13_2_auth_flow.mmd": """sequenceDiagram
    autonumber
    actor Client as Client Browser
    participant API as FastAPI Auth Endpoint
    participant JWT as JWT Utility (PyJWT)
    participant DB as User Database
    participant Middleware as RoleChecker Middleware

    Client->>API: POST /auth/login {username, password}
    API->>DB: Query User Record & Password Hash
    DB-->>API: User Record Found (bcrypt hashed)
    API->>JWT: Generate Access Token (30m) & Refresh Token (7d)
    JWT-->>API: Signed HS256 Tokens
    API-->>Client: Return {access_token, refresh_token, role}

    Note over Client, Middleware: Subsequent Authenticated Requests
    Client->>Middleware: POST /chat (Header: Bearer <access_token>)
    Middleware->>JWT: Decode & Validate HS256 Token Signature
    JWT-->>Middleware: Claims Valid (sub, role, exp)
    Middleware->>Middleware: Verify Role Permitted (e.g. EMPLOYEE)
    Middleware-->>API: Request Approved — Inject User Context
""",

    "fig_14_1_er_diagram.mmd": """erDiagram
    USER ||--o{ TICKET : "creates"
    USER {
        int id PK
        string username UK
        string role
        string hashed_password
        boolean is_active
    }

    TICKET ||--o{ SLA_ESCALATION : "tracks"
    TICKET ||--o{ APPROVAL_HISTORY : "requires"
    TICKET ||--o{ TICKET_TIMELINE : "logs"
    TICKET {
        string ticket_id PK
        string servicenow_id
        string servicenow_number
        string category
        string status
        string sla_state
        string approval_status
    }

    SLA_ESCALATION {
        int id PK
        string ticket_id FK
        int escalation_level
        string notified_recipients
        datetime escalated_at
    }

    APPROVAL_HISTORY {
        int id PK
        string ticket_id FK
        string action
        string performed_by
        datetime performed_at
    }

    AUDIT_LOG {
        int id PK
        string correlation_id
        string event_type
        string actor
        string payload_hash
        text payload_json
        datetime timestamp
    }
""",

    "fig_15_1_api_lifecycle.mmd": """sequenceDiagram
    autonumber
    actor Client as Client Browser
    participant Nginx as Nginx Ingress
    participant SizeMW as SizeLimiter Middleware
    participant RateMW as RateLimiter Middleware
    participant AuthMW as JWT / RBAC Middleware
    participant Guard as PromptGuard Engine
    participant Graph as LangGraph Engine

    Client->>Nginx: POST /chat (HTTP Body + Bearer Token)
    Nginx->>SizeMW: Forward Payload
    SizeMW->>SizeMW: Verify Body Size <= 512 KB
    SizeMW->>RateMW: Size Check PASSED
    RateMW->>RateMW: Verify Sliding Window Limit (30 req/min)
    RateMW->>AuthMW: Rate Limit PASSED
    AuthMW->>AuthMW: Validate JWT Signature & Role (EMPLOYEE)
    AuthMW->>Guard: Authentication PASSED
    Guard->>Guard: Scan Prompt for Injection Rules (HIGH / MEDIUM / LOW)
    Guard->>Graph: Injection Check PASSED -> Execute StateGraph
    Graph-->>Client: HTTP 200 OK (Response + Session State)
""",

    "fig_16_1_deployment_topology.mmd": """flowchart TB
    subgraph Host["Bridgestone Enterprise Host Node (Production)"]
        subgraph Net["Docker Bridge Network: bridgestone-network"]
            subgraph ProxyTier["Ingress Layer"]
                NGINX["bridgestone-nginx-prod\n(Nginx 1.25 Alpine)\nPorts: 80, 443 Exposed"]
            end

            subgraph AppTier["Application Tier (Internal Network)"]
                FE["bridgestone-frontend-prod\n(Next.js 16 Node Server)\nPort: 3000 Internal"]
                BE["bridgestone-backend-prod\n(FastAPI + Uvicorn Async Engine)\nPort: 8000 Internal"]
            end

            subgraph DataTier["Data Tier (Internal Network)"]
                PG[("bridgestone-postgres-prod\n(PostgreSQL 14 DB)\nPort: 5432 Internal")]
                REDIS[("bridgestone-redis-prod\n(Redis Cache Server)\nPort: 6379 Internal")]
            end

            subgraph ObsTier["Observability Tier (Restricted)"]
                PROM["Prometheus Server\nPort: 9090"]
                GRAF["Grafana Dashboard\nPort: 3001"]
            end
        end
    end

    NGINX --> FE
    NGINX --> BE
    BE --> PG
    BE --> REDIS
    BE --> PROM
    PROM --> GRAF
"""
}

def write_and_render():
    print("Writing diagram files...")
    for filename, code in DIAGRAMS.items():
        filepath = os.path.join(DIAGRAMS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        
        png_filename = filename.replace(".mmd", ".png")
        png_path = os.path.join(DIAGRAMS_DIR, png_filename)
        
        cmd = f'cmd /c "npx -y @mermaid-js/mermaid-cli -i "{filepath}" -o "{png_path}" -c "{config_path}" -b "#0b0f19" -s 2"'
        print(f"Rendering {png_filename}...")
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  SUCCESS: {png_filename}")
        else:
            print(f"  ERROR rendering {filename}: {res.stderr}")

if __name__ == "__main__":
    write_and_render()
