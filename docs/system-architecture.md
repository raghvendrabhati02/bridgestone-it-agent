# Bridgestone IT Agent — System Architecture Document

This document provides a technical description of the Bridgestone IT Agent's multi-agent runtime, state management, database schema design, and external API adapter models.

---

## 1. High-Level Architectural Layout

The Bridgestone IT Agent POC platform consists of three main decoupled layers:

1. **User Presentation (Frontend):** 
   * Next.js 14 Web UI.
   * Leverages server-side rendering for administrative logs and reactive client-side rendering for realtime chat conversations.
2. **Business Orchestration (Backend Service):**
   * Python FastAPI web service.
   * Exposes stateless REST endpoints and invokes LangGraph StateGraph state machines to process messages.
3. **Database & Cache (Storage):**
   * PostgreSQL (production) or SQLite (local development fallback).
   * Redis for active caches (session tokens, locks, metrics registries).

---

## 2. Multi-Agent Pipeline (LangGraph Workflow)

```mermaid
graph TD
    UserQuery[User Query] --> Router{Router Node}
    
    Router -->|Small Talk / Greeting| ConvAgent[Conversation Agent]
    ConvAgent --> END
    
    Router -->|IT Issue / Request| MemoryNode[Memory Node]
    MemoryNode --> ContextRouter{Context Router}
    
    ContextRouter -->|Query Ticket Status| StatusNode[Ticket Status Node]
    StatusNode --> END
    
    ContextRouter -->|Service Request| SRNode[Service Request Node]
    SRNode --> END
    
    ContextRouter -->|Troubleshoot Issue| IntentNode[Intent Node]
    IntentNode --> DiagnosticCheck{Diagnostic Interview Check}
    
    DiagnosticCheck -->|Needs Details| AskQuestions[Diagnostic Interview Node]
    AskQuestions --> END
    
    DiagnosticCheck -->|Sufficient| PlannerNode[Planner Node]
    PlannerNode --> ToolNode[Tool Execution Node]
    ToolNode --> MultiStepNode{Multi-Step Node}
    
    MultiStepNode -->|Iterate / More Tools| ToolNode
    MultiStepNode -->|Complete| RCNode[Root Cause Node]
    
    RCNode --> ReflectionNode[Reflection Agent]
    ReflectionNode --> DecisionNode[Decision Node]
    
    DecisionNode -->|Create Ticket| CreateTicket[Ticket Node]
    CreateTicket --> Lifecycle[Ticket Lifecycle Node]
    Lifecycle --> Assign[Assignment Node]
    Assign --> Notify[Notification Node]
    Notify --> SLANode[SLA Node]
    SLANode --> END
    
    DecisionNode -->|Execute privileged action| ApprovalNode{Approval Node}
    ApprovalNode -->|Approved| ActionNode[Action Execution Node]
    ActionNode --> Notify
    
    ApprovalNode -->|Rejected / Denied| Notify
```

---

## 3. Database Schema Blueprint

```mermaid
erDiagram
    SESSIONS {
        string session_id PK
        string category
        int current_step
        string status
        boolean approval_required
        string approval_status
        string recommended_action
        json action_result
        json tool_result
        string active_ticket
        string active_issue
        string active_request
        string conversation_goal
        string last_action
        datetime created_at
    }
    
    CONVERSATIONS {
        int id PK
        string session_id FK
        text user_message
        text agent_response
        string category
        datetime created_at
    }
    
    TICKETS {
        string ticket_id PK
        string category
        text description
        text issue_description
        string priority
        int sla_hours
        string status
        string assigned_team
        string assigned_engineer
        string created_by
        string correlation_id
        datetime created_at
        datetime last_customer_response_at
    }
    
    APPROVAL_HISTORY {
        int id PK
        string session_id FK
        string recommended_action
        string approval_status
        string correlation_id
        datetime created_at
    }

    SESSIONS ||--o{ CONVERSATIONS : "has turns"
    SESSIONS ||--o| TICKETS : "resolves in"
    SESSIONS ||--o{ APPROVAL_HISTORY : "tracks approvals"
```

---

## 4. Integration Adapter Model

To ensure clean isolation and security:
* **ServiceNowAdapter:** Manages mapping internal database tickets to target enterprise incident numbers. Translates ticket statuses (OPEN, WAITING_FOR_USER, RESOLVED) to ServiceNow states.
* **MicrosoftGraphAdapter / Entra ID:** Performs account lookup checks (locked status, password expiration, group membership attributes) against mocked active directories.
* **ActiveDirectoryAdapter:** Integrates AD check tools into the automated tool agent nodes.
