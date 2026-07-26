# Security Policy

> **Project:** Bridgestone IT AI Assistant  
> **Last updated:** 2026-07-26

The security of the **Bridgestone IT AI Assistant** is a top priority. We appreciate the work of security researchers and developers in identifying potential vulnerabilities responsibly.

---

## Supported Versions

Only the latest stable release receives active security patches and updates:

| Version | Supported | Notes |
|---|---|---|
| `v1.0.0` | :white_check_mark: Yes | Active stable release |
| `< 1.0.0` | :x: No | Pre-release development tags |

---

## Security Architecture Overview

The system incorporates defensive security controls at multiple layers:

1. **Authentication & Authorization:**
   - Stateless JWT Bearer token authentication with configurable secret key (`SECRET_KEY`).
   - Role-Based Access Control (RBAC) enforced via FastAPI `RoleChecker` dependencies across `EMPLOYEE`, `MANAGER`, and `ADMIN` tiers.

2. **Prompt Injection Protection (PromptGuard):**
   - Pre-filters input chat turns through risk scoring before LLM model invocation.
   - High-risk prompt injections trigger immediate HTTP 400 rejection and log security audit events.

3. **Rate Limiting:**
   - Sliding-window rate limit protection on authentication (`/auth/login`) and AI chat (`/chat`) endpoints.

4. **ServiceNow OAuth2 Security:**
   - Encrypted client credentials flow with automatic token renewal and SSL verification options.

5. **Audit Logging:**
   - Immutable security event repository (`security_events`) recording logins, password failures, and RBAC permission denials (`rbac_audit_logs`).

---

## Reporting a Vulnerability

**Do NOT file public GitHub issues for security vulnerabilities.**

If you discover a security vulnerability, please report it privately:

1. **Email:** Send details to the project maintainers or email `security@bridgestone-it-agent.local` (or contact project author [Raghvendra Bhati](https://github.com/raghvendrabhati02)).
2. **Details to Include:**
   - Description of the vulnerability and potential impact.
   - Step-by-step proof-of-concept (PoC) instructions or request payload to reproduce the issue.
   - Affected system components (FastAPI endpoints, PromptGuard filter, JWT validation, ServiceNow client).

### Response Timeline
- **Acknowledgement:** Within 48 hours of report receipt.
- **Triage & Assessment:** Within 5 business days.
- **Fix Release:** Vulnerability patch will be published as a minor release tag.

---

## Environment & Secrets Hygiene

When deploying or contributing to this project:

- **Never commit production API keys**, JWT secret strings, or live ServiceNow OAuth credentials to version control.
- Use `.env` files locally and environment secrets in production.
- Sanitize all log output to prevent logging raw JWT tokens or password strings.
