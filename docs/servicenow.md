# ServiceNow Integration

> **Project:** Bridgestone IT AI Assistant · **Last updated:** 2026-07-26

---

## Overview

ServiceNow is the live ITSM system of record for this project. The backend creates incidents in a real ServiceNow developer instance automatically when the AI agent determines a ticket must be raised. All fields are validated against live ServiceNow metadata before submission.

---

## Incident Creation Pipeline

```mermaid
flowchart LR
    A[User Message] --> B["ClassificationService\n(Gemini / Claude)"]
    B --> C["IncidentEnrichmentService\n(metadata resolution)"]
    C --> D["FieldMappingService\n(SN payload builder)"]
    D --> E["ServiceNowMetadataValidator\n(live field validation)"]
    E --> F["ServiceNowClient\n(OAuth2 REST POST)"]
    F --> G[(ServiceNow Instance)]
    G --> H[INC number returned]
    H --> I[Persisted in DB + notification sent]
```

---

## Authentication

`ServiceNowClient` (`services/servicenow_client.py`) uses **OAuth 2.0 Client Credentials** as the primary authentication method, with automatic **HTTP Basic Auth** fallback:

1. `POST /oauth_token.do` with `client_id` and `client_secret`.
2. Access token cached in-memory with automatic expiry detection.
3. If OAuth fails: falls back to `HTTPBasicAuth` using `SERVICENOW_USERNAME` / `SERVICENOW_PASSWORD`.

---

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `SERVICENOW_INSTANCE_URL` | Full URL to the ServiceNow instance | Yes |
| `SERVICENOW_USERNAME` | API username (Basic Auth / OAuth ROPC) | Yes |
| `SERVICENOW_PASSWORD` | API password | Yes |
| `SERVICENOW_CLIENT_ID` | OAuth application client ID | For OAuth |
| `SERVICENOW_CLIENT_SECRET` | OAuth application client secret | For OAuth |
| `SERVICENOW_USE_MOCK` | Set to `true` to disable live calls | Optional |

---

## Field Mapping

| ServiceNow Field | Source | Notes |
|---|---|---|
| `short_description` | `ClassificationService` output | AI-generated concise summary |
| `description` | `ClassificationService` output | Full narrative |
| `category` | `FieldMappingService` + `ServiceNowMetadataValidator` | Validated against live SN categories |
| `subcategory` | `FieldMappingService` + `ServiceNowMetadataValidator` | Validated against live SN subcategories |
| `contact_type` | Fixed: `virtual_agent` | Identifies AI-sourced incidents |
| `u_type` | `FieldMappingService` | Mapped from issue category (e.g. `Digital Workplace`) |
| `assignment_group` | `ServiceNowChoiceResolver` | Resolved to `sys_id` from group display name |
| `urgency` | `SlaService` | Calculated from priority — not set by AI |
| `impact` | `SlaService` | Calculated from priority — not set by AI |
| `cmdb_ci` | `ServiceNowChoiceResolver` | Resolved to CMDB CI `sys_id` |
| `caller_id` | Current user username | |

---

## ServiceNow Metadata Validator

`ServiceNowMetadataValidator` (`services/servicenow_metadata_validator.py`) validates every configured field value against the live ServiceNow instance before any incident is submitted.

### ServiceNow Metadata Cache

`ServiceNowMetadataCache` (`services/servicenow_metadata_cache.py`) implements a TTL-based in-memory cache:

- **TTL:** 3600 seconds (configurable)
- **Cached data:** Categories, subcategories (as `sys_choice` records), assignment groups (`sys_user_group`), CMDB CIs, contact types, urgency/impact/priority values
- **Refresh:** On TTL expiry or on demand via `GET /servicenow/validate`

### Validated Categories (confirmed live)

| Category | Status |
|---|---|
| `Software` | ✅ VALID |
| `Hardware` | ✅ VALID |
| `Microsoft 365` | ✅ VALID |
| `E-mail` | ✅ VALID |
| `Network` | ✅ VALID |
| `Printer` | ✅ VALID |
| `Password/Access` | ✅ VALID |
| `Security` | ✅ VALID |
| `BSID Domain` | ✅ VALID |
| `CyberArk PAM` | ✅ VALID |
| `Mobile Devices` | ✅ VALID |

### Validated Assignment Groups (confirmed live)

| Group | Status |
|---|---|
| `IT Support` | ✅ VALID |
| `Network Team` | ✅ VALID |
| `Hardware Team` | ✅ VALID |
| `Security Team` | ✅ VALID |
| `Identity Team` | ✅ VALID |
| `Mobile Team` | ✅ VALID |

### ServiceNow Choice Resolver

`ServiceNowChoiceResolver` converts human-readable labels to the `sys_id` values required by the ServiceNow REST API:

```python
# Example: "IT Support" → "0a4335ffdbaa1c104b1818fe3b96193f"
resolver.resolve_assignment_group("IT Support")
```

---

## Mock Mode

Set `SERVICENOW_USE_MOCK=true` to disable all live ServiceNow calls. In mock mode:

- Incidents are assigned a generated `INC0000XXX` number
- No HTTP calls are made to ServiceNow
- Metadata validation uses locally cached configuration instead of live API

This is the default for local development if ServiceNow credentials are not provided.

---

## Validation Report

The full validation report for all configured fields is available at runtime:

```
GET /servicenow/validate
Requires: Authorization: Bearer <admin_token>
```

Response includes per-field validation status, suggestions for invalid values, and cache metadata.

---

## Troubleshooting

| Symptom | Resolution |
|---|---|
| `401 Unauthorized` from ServiceNow | Check `SERVICENOW_CLIENT_ID`, `SERVICENOW_CLIENT_SECRET`, `SERVICENOW_USERNAME`, `SERVICENOW_PASSWORD` |
| Field validation failures | Run `GET /servicenow/validate` and check the report for invalid values |
| `cmdb_ci` field rejected | The CI may not exist in your ServiceNow instance; check `CMDB CIs Validation` section of the report |
| Subcategory `MISSING` | Subcategories for some categories are not pre-seeded in all developer instances; omit subcategory or add the values to the SN instance |
| Want to switch to mock mode | Set `SERVICENOW_USE_MOCK=true` and restart the backend |

---

## Incident Lifecycle in ServiceNow

| Operation | REST Method | SN Endpoint |
|---|---|---|
| Create incident | `POST` | `/api/now/table/incident` |
| Get incident | `GET` | `/api/now/table/incident/{sys_id}` |
| Update incident | `PATCH` | `/api/now/table/incident/{sys_id}` |
| Close incident | `PATCH` | `/api/now/table/incident/{sys_id}` with `state: 7` |

---

## Related Documents

- [Architecture](./architecture.md) — Service map and adapter layer
- [AI Workflow](./ai-workflow.md) — Classification pipeline and ticket node
- [API Reference](./API.md) — ServiceNow endpoints
