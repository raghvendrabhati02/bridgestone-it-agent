# Changelog

All notable changes to the Bridgestone IT AI Assistant project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-26

### Added
- **AI Conversational IT Assistant**: Multi-turn conversational support powered by Google Gemini and an 18-node LangGraph troubleshooting pipeline.
- **Multi-Turn Conversation Support**: Persistent session state machine backed by SQLite database and Redis memory cache.
- **Knowledge Base Integration**: Vectorized and semantic Knowledge Base retrieval for automated issue diagnostic steps.
- **AI Issue Classification**: Automatic issue categorization, priority determination, subcategory assignment, and CMDB CI mapping.
- **ServiceNow Integration**: Bidirectional synchronization with ServiceNow Table API, OAuth2 authentication, and runtime metadata validation.
- **Automatic Ticket Creation**: Dynamic creation of Incident (`INC`) and Service Request (`REQ`) tickets with SLA monitoring.
- **Manager Approval Workflow**: Manager Portal interface for pending request reviews, approvals, rejections, and approved ticket tracking.
- **Admin Approval Workflow**: IT Admin Queue view for full enterprise request management and fulfillment.
- **Temporary Admin Access (Mock)**: Enterprise Admin Access Card issuing temporary administrator credentials with a 15-minute countdown timer (designed for future LAPS / CyberArk PAM integration).
- **Role-Based Access Control (RBAC)**: Strict role enforcement across `EMPLOYEE`, `MANAGER`, and `ADMIN` user tiers.
- **Audit Logging**: Immutable security event and RBAC audit logs with correlation ID tracking.
- **Analytics Dashboard**: Real-time executive KPIs, ticket resolution metrics, incident clustering, and SLA compliance dashboards.
- **Security Middleware**: CORS policy, JWT authentication, rate limiting, and input sanitization.
- **Prompt Injection Protection**: PromptGuard security filter analyzing input risk scores to block malicious prompts.
- **Rate Limiting**: Sliding window rate limit protection on authentication and chat endpoints.
- **Documentation**: Professional engineering documentation suite including `README.md`, `architecture.md`, `ai-workflow.md`, `servicenow.md`, `API.md`, and `EndToEndTestingChecklist.md`.

### Changed
- **Refactored Conversation Workflow**: Enhanced state transitions between understanding, diagnosing, verifying, ticket confirmation, and resolution phases.
- **Improved Provider Architecture**: Resilient LLM provider layer with fast failover from `gemini-3.5-flash` to `gemini-3.1-flash-lite` on quota/rate-limit events.
- **Updated ServiceNow Metadata Validation**: Runtime validator enforcing valid field mappings against ServiceNow sys_choice metadata with graceful fallbacks.
- **Improved Error Handling**: Standardized error payloads across all FastAPI endpoints with detailed context log traces.
- **Updated Documentation**: Comprehensive review ensuring all API endpoints, workflows, and test cases reflect 100% of current codebase behavior.

### Fixed
- **Database Schema Migration Issue**: Added missing `approved_by`, `approved_at`, and `approval_notes` columns to SQLite `tickets` table using safe `ALTER TABLE` operations.
- **Ticket Persistence Issue**: Resolved object attribute vs dict key mismatch in ServiceNow creation response handling inside `TicketService`.
- **Approval Workflow Bugs**: Fixed Manager Portal filtering so newly approved tickets remain visible in the "Approved Requests" tab.
- **AI Provider Retry/Fallback Issues**: Fixed exception handling for Gemini API rate limits (`RESOURCE_EXHAUSTED` / HTTP 429) to fail fast and trigger model fallback without blocking response threads.
- **Session State Issues**: Resolved cache hit phase restoration and session manager deserialization bugs.
