# Bridgestone IT Agent

## Objective

Build an Agentic AI system that acts as the first level IT support for employees before ServiceNow ticket creation.

## Workflow

Employee
↓
AI Agent
↓
Issue Understanding
↓
Knowledge Search
↓
Troubleshooting
↓
Solved?

YES → Close Session

NO → Create ServiceNow Ticket
↓
Assign Team
↓
Track SLA
↓
Notify Employee
↓
Close Ticket

## Technology Stack

Frontend:
- Next.js
- TypeScript
- Tailwind

Backend:
- FastAPI

Agent Framework:
- LangGraph

Vector DB:
- Qdrant

Database:
- PostgreSQL

Cache:
- Redis

LLM:
- Qwen 2.5

Deployment:
- Docker
