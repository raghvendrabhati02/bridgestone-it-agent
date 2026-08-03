# AI Architecture & Governance Guide (Version 2.0)

## 1. Overview
The Bridgestone Enterprise AI Service Desk Platform uses an asynchronous orchestrator architecture powered by Google Gemini (with Anthropic Claude fallback options) and LangGraph workflow orchestration.

---

## 2. Core AI Modules

```
[User Input] ──► [Prompt Guard / XSS Sanitizer] ──► [Intent Router]
                                                         │
               ┌─────────────────────────────────────────┼─────────────────────────────────────────┐
               ▼                                         ▼                                         ▼
      [ITSM Classifier]                         [Knowledge RAG Engine]                       [Diagnostic Engine]
  (Category, Priority, Impact)                    (Articles, Troubleshooting)                  (Resolution Scripts)
               │                                         │                                         │
               └─────────────────────────────────────────┼─────────────────────────────────────────┘
                                                         ▼
                                                [Response Builder] ──► [LLM Output]
```

- **Prompt Guard** (`app/services/prompt_guard.py`): Screens against prompt injection attacks.
- **Intent Router** (`app/services/intent_router.py`): Categorizes user input into predefined intent categories.
- **ITSM Classifier** (`app/services/itsm_classifier.py`): Extracts ITSM metadata (Category, Subcategory, Urgency, Impact).
- **Knowledge RAG Engine** (`app/services/knowledge_service.py`): Indexes KB articles and retrieves relevant troubleshooting guidance.
- **Diagnostic Engine** (`app/services/diagnostic_engine.py`): Guides multi-step troubleshooting flows.
- **Response Builder** (`app/services/response_builder.py`): Formats natural language responses.

---

## 3. AI Evaluation & Metrics Framework

The AI Evaluation Service (`app/services/ai_evaluation_service.py`) measures performance across 10 dimensions:

| Metric | Target | Formula / Source |
|---|---|---|
| **Intent Classification Accuracy** | > 95.0% | Correctly identified intent / total requests |
| **Category Accuracy** | > 94.0% | Matched ITSM category / total classified |
| **Assignment Accuracy** | > 92.0% | Correct assignment group routing / total |
| **Knowledge Retrieval Success** | > 90.0% | Articles referenced that resolved issue / total RAG queries |
| **Resolution Success Rate** | > 85.0% | AI-resolved tickets / total opened tickets |
| **Escalation Rate** | < 15.0% | L2/L3 escalated tickets / total tickets |
| **Average Conversation Length** | < 4.5 turns | Sum(turns) / total completed sessions |
| **Average Resolution Time** | < 15 min | Sum(resolution_time) / total resolved tickets |
| **Fallback Rate** | < 5.0% | Triggered fallback provider / total LLM calls |
| **Confidence Score Distribution** | High Tiers | Breakdown of LLM output confidence (>0.9, 0.8-0.9, 0.7-0.8, <0.7) |

---

## 4. Prompt Management & Versioning

Prompt Management (`app/services/prompt_management_service.py`) provides:
1. **Dynamic Editing**: Update prompts without code deployments.
2. **Versioning & History**: Automatic version numbers (`1.0` -> `1.1`) and rollback snapshots.
3. **Template Preview**: Previews prompt strings with variable substitutions (`{user}`, `{issue}`).

---

## 5. Multi-Agent Preparedness (Extension Interfaces)

Module `app/agents/multi_agent_interface.py` defines extension points for future V2.X swarm capabilities:
- `TriageAgentInterface`: Autonomous classification and screening.
- `DiagnosticAgentInterface`: RAG retrieval and troubleshooting execution.
- `ActionAgentInterface`: ServiceNow ticket operations and active directory actions.
- `MultiAgentCoordinatorInterface`: Swarm routing and execution dispatch.
