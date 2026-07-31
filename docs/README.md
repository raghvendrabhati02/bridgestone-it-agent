# Bridgestone IT AI Assistant — Documentation

> **Last updated:** 2026-07-26

This folder contains all technical and user-facing documentation for the Bridgestone IT AI Assistant.

---

## Document Index

| Document | Audience | Description |
|---|---|---|
| [Architecture.md](./Architecture.md) | Developer | System tiers, service map, middleware chain, ticket lifecycle, SLA engine |
| [ai-workflow.md](./ai-workflow.md) | Developer | LangGraph pipeline (18 nodes), classification, routing logic, privileged install flow |
| [servicenow.md](./servicenow.md) | Developer | Incident pipeline, OAuth2 auth, metadata validation, field mapping |
| [Database.md](./Database.md) | Developer | All ORM models, schema, auto-migration, connection configuration |
| [Security.md](./Security.md) | Developer | JWT, RBAC, prompt injection guard, rate limiting, audit logging |
| [API.md](./API.md) | Developer | All REST endpoints with request/response schemas |
| [Deployment.md](./Deployment.md) | DevOps | Local setup, Docker deployment, environment variables, production checklist |
| [EndToEndTestingChecklist.md](./EndToEndTestingChecklist.md) | QA | Test scenarios for all workflows including the approval chain |
| [UserGuide.md](./UserGuide.md) | End user | How to use the employee, manager, and admin portals |
| [RELEASE_NOTES_v1.0.0.md](./RELEASE_NOTES_v1.0.0.md) | All | Release notes and features summary for Initial Stable Release v1.0.0 |
| [CHANGELOG.md](../CHANGELOG.md) | All | Project changelog following Keep a Changelog standard |

---

## Screenshots

Project screenshots are stored in the `screenshots/` directory and embedded in the [README.md](../README.md) at the root of the repository.

---

## Quick Links

- [Project README](../README.md) — Overview, installation, and demo flow
- [Backend entry point](../backend/app/main.py)
- [LangGraph graph definition](../backend/app/graph/graph.py)
- [ServiceNow client](../backend/app/services/servicenow_client.py)
- [SLA escalation engine](../backend/app/services/sla_escalation_service.py)
