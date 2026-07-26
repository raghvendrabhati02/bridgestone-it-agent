from prometheus_client import Counter, Gauge, Histogram

# In-memory tracking lists for /system-status API metrics
REQUEST_TIMESTAMPS = []
ERROR_TIMESTAMPS = []
API_LATENCIES = []
AI_LATENCIES = []

# ==============================================================================
# 1. HTTP REQUEST METRICS
# ==============================================================================
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP Requests received",
    ["method", "path"]
)

HTTP_FAILURES_TOTAL = Counter(
    "http_failures_total",
    "Total HTTP requests resulting in failures",
    ["method", "path", "status_code"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP Request processing latency in seconds",
    ["method", "path"]
)

# ==============================================================================
# 2. SECURITY METRICS
# ==============================================================================
SECURITY_LOGINS_TOTAL = Counter(
    "security_logins_total",
    "Total successful logins",
    ["username"]
)

SECURITY_FAILED_LOGINS_TOTAL = Counter(
    "security_failed_logins_total",
    "Total failed login attempts",
    ["username"]
)

SECURITY_PERMISSION_DENIED_TOTAL = Counter(
    "security_permission_denied_total",
    "Total permission denied / role check blocks",
    ["username"]
)

SECURITY_JWT_EXPIRED_TOTAL = Counter(
    "security_jwt_expired_total",
    "Total requests with expired JWT tokens"
)

SECURITY_UNAUTHORIZED_TOTAL = Counter(
    "security_unauthorized_total",
    "Total requests rejected due to invalid or missing credentials"
)

# ==============================================================================
# 3. LANGGRAPH NODE METRICS
# ==============================================================================
AGENT_EXECUTION_TIME = Histogram(
    "agent_execution_duration_seconds",
    "Execution duration for LangGraph agent nodes in seconds",
    ["agent_name"]
)

# ==============================================================================
# 4. LLM / GEMINI METRICS
# ==============================================================================
LLM_REQUESTS_TOTAL = Counter(
    "llm_requests_total",
    "Total LLM API requests sent"
)

LLM_SUCCESS_TOTAL = Counter(
    "llm_success_total",
    "Total successful LLM API responses"
)

LLM_FAILURES_TOTAL = Counter(
    "llm_failures_total",
    "Total failed LLM API requests",
    ["error_type"]
)

LLM_LATENCY_SECONDS = Histogram(
    "llm_latency_seconds",
    "LLM API response latency in seconds"
)

LLM_REQUEST_DURATION_SECONDS = Histogram(
    "llm_request_duration_seconds",
    "LLM Request processing latency in seconds",
    ["model", "fallback_used"]
)

LLM_VERIFY_DURATION_SECONDS = Histogram(
    "llm_verify_duration_seconds",
    "LLM Verification processing latency in seconds"
)

LLM_FALLBACK_DURATION_SECONDS = Histogram(
    "llm_fallback_duration_seconds",
    "LLM Fallback request processing latency in seconds",
    ["target_model", "fallback_model"]
)


LLM_TOKEN_USAGE_TOTAL = Counter(
    "llm_token_usage_total",
    "Total LLM tokens consumed",
    ["token_type"]  # "prompt_tokens" or "candidate_tokens"
)

LLM_RATE_LIMIT_ERRORS_TOTAL = Counter(
    "llm_rate_limit_errors_total",
    "Total rate limiting errors (HTTP 429) hit on LLM API"
)

LLM_FALLBACK_EVENTS_TOTAL = Counter(
    "llm_fallback_events_total",
    "Total agent fallback trigger occurrences"
)

# Verification, initialization, and fallback metrics
LLM_VERIFY_TOTAL = Counter(
    "llm_verify_total",
    "Total verification attempts"
)

LLM_VERIFY_SUCCESS_TOTAL = Counter(
    "llm_verify_success_total",
    "Total successful verification attempts"
)

LLM_VERIFY_FAILURE_TOTAL = Counter(
    "llm_verify_failure_total",
    "Total failed verification attempts"
)

LLM_PROVIDER_INITIALIZATION_TOTAL = Counter(
    "llm_provider_initialization_total",
    "Total provider initialization occurrences"
)

LLM_MODEL_FALLBACK_TOTAL = Counter(
    "llm_model_fallback_total",
    "Total fallback events to secondary models",
    ["target_model", "fallback_model", "reason"]
)


# ==============================================================================
# 5. BUSINESS OPERATIONS METRICS
# ==============================================================================
BUSINESS_TICKETS_CREATED_TOTAL = Counter(
    "business_tickets_created_total",
    "Total tickets created in the system"
)

BUSINESS_TICKETS_RESOLVED_TOTAL = Counter(
    "business_tickets_resolved_total",
    "Total support tickets successfully resolved/closed"
)

BUSINESS_APPROVALS_TOTAL = Counter(
    "business_approvals_total",
    "Total approvals processed",
    ["status"]  # "requested", "approved", or "rejected"
)

BUSINESS_ACTIONS_EXECUTED_TOTAL = Counter(
    "business_actions_executed_total",
    "Total automated corrective actions executed"
)

BUSINESS_NOTIFICATIONS_SENT_TOTAL = Counter(
    "business_notifications_sent_total",
    "Total notification triggers sent to employees/teams"
)

BUSINESS_SLA_BREACHES_TOTAL = Counter(
    "business_sla_breaches_total",
    "Total SLA target breach occurrences"
)

# ==============================================================================
# 6. DATABASE METRICS
# ==============================================================================
DB_CONNECTIONS_ACTIVE = Gauge(
    "db_connections_active",
    "Current active database connection connections count"
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query execution latency in seconds"
)

DB_FAILURES_TOTAL = Counter(
    "db_failures_total",
    "Total database queries resulting in driver failures"
)

DB_TRANSACTIONS_TOTAL = Counter(
    "db_transactions_total",
    "Total database transactions commits"
)

# ==============================================================================
# 7. REDIS METRICS
# ==============================================================================
REDIS_AVAILABILITY = Gauge(
    "redis_availability",
    "Redis connectivity status (1 = healthy, 0 = down)"
)

REDIS_CACHE_HITS_TOTAL = Counter(
    "redis_cache_hits_total",
    "Total Redis cache read hits"
)

REDIS_CACHE_MISSES_TOTAL = Counter(
    "redis_cache_misses_total",
    "Total Redis cache read misses"
)

REDIS_SESSION_RESTORATIONS_TOTAL = Counter(
    "redis_session_restorations_total",
    "Total sessions loaded and restored from database"
)

# ==============================================================================
# 8. SERVICENOW INTEGRATION METRICS
# ==============================================================================
SERVICENOW_REQUESTS_TOTAL = Counter(
    "servicenow_requests_total",
    "Total requests sent to ServiceNow REST APIs",
    ["operation"]
)

SERVICENOW_FAILURES_TOTAL = Counter(
    "servicenow_failures_total",
    "Total failed requests to ServiceNow REST APIs",
    ["operation", "error_type"]
)

SERVICENOW_LATENCY_SECONDS = Histogram(
    "servicenow_latency_seconds",
    "ServiceNow REST API response latency in seconds",
    ["operation"]
)

INCIDENTS_CREATED_TOTAL = Counter(
    "incidents_created_total",
    "Total ServiceNow incidents created successfully"
)

SERVICE_REQUESTS_CREATED_TOTAL = Counter(
    "service_requests_created_total",
    "Total ServiceNow service requests created successfully"
)

# ==============================================================================
# 9. MICROSOFT GRAPH INTEGRATION METRICS
# ==============================================================================
GRAPH_REQUESTS_TOTAL = Counter(
    "graph_requests_total",
    "Total requests sent to Microsoft Graph APIs",
    ["operation"]
)

GRAPH_FAILURES_TOTAL = Counter(
    "graph_failures_total",
    "Total failed requests to Microsoft Graph APIs",
    ["operation", "error_type"]
)

GRAPH_LATENCY_SECONDS = Histogram(
    "graph_latency_seconds",
    "Microsoft Graph API response latency in seconds",
    ["operation"]
)

GRAPH_MAILBOX_CHECKS_TOTAL = Counter(
    "graph_mailbox_checks_total",
    "Total Microsoft Graph mailbox check operations"
)

GRAPH_LICENSE_CHECKS_TOTAL = Counter(
    "graph_license_checks_total",
    "Total Microsoft Graph license check operations"
)

# ==============================================================================
# 10. AZURE AD / ENTRA ID INTEGRATION METRICS
# ==============================================================================
AD_REQUESTS_TOTAL = Counter(
    "ad_requests_total",
    "Total requests sent to Active Directory / Entra ID APIs",
    ["operation"]
)

AD_FAILURES_TOTAL = Counter(
    "ad_failures_total",
    "Total failed requests to Active Directory / Entra ID APIs",
    ["operation", "error_type"]
)

AD_LATENCY_SECONDS = Histogram(
    "ad_latency_seconds",
    "Active Directory / Entra ID API response latency in seconds",
    ["operation"]
)

GROUP_CHECKS_TOTAL = Counter(
    "group_checks_total",
    "Total Entra ID group membership check operations"
)

ACCESS_CHECKS_TOTAL = Counter(
    "access_checks_total",
    "Total Entra ID access validation check operations"
)

# ==============================================================================
# 11. TOOL EXECUTION METRICS
# ==============================================================================
TOOL_EXECUTION_TOTAL = Counter(
    "tool_execution_total",
    "Total tool executions dispatched by the tool agent",
    ["tool_name", "status"]          # status: "success" | "failure"
)

TOOL_EXECUTION_DURATION_SECONDS = Histogram(
    "tool_execution_duration_seconds",
    "Tool execution latency in seconds",
    ["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

TOOL_RETRIES_TOTAL = Counter(
    "tool_retries_total",
    "Total tool execution retries",
    ["tool_name"]
)

# ==============================================================================
# 12. PROVIDER-LEVEL METRICS (per provider + model)
# ==============================================================================
PROVIDER_REQUESTS_TOTAL = Counter(
    "provider_requests_total",
    "Total requests sent to each AI provider",
    ["provider", "model"]
)

PROVIDER_RETRIES_TOTAL = Counter(
    "provider_retries_total",
    "Total retry attempts made against each AI provider",
    ["provider", "model"]
)

PROVIDER_QUOTA_FAILURES_TOTAL = Counter(
    "provider_quota_failures_total",
    "Total quota / rate-limit failures per provider",
    ["provider"]
)

PROVIDER_LATENCY_SECONDS = Histogram(
    "provider_latency_seconds",
    "End-to-end latency per provider call in seconds",
    ["provider", "model", "fallback_used"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)

# ==============================================================================
# 13. PIPELINE SPAN METRICS (per service + provider + status)
# ==============================================================================
PIPELINE_SPAN_DURATION_SECONDS = Histogram(
    "pipeline_span_duration_seconds",
    "End-to-end latency of each pipeline service stage in seconds",
    ["service", "provider", "status"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)
# Label reference:
#   service  — component name: "classification", "enrichment", "ticket_summary",
#              "ticket_service", "servicenow_api", "conversation", "http_request"
#   provider — AI provider in scope, or "none" / "servicenow" / "unknown"
#   status   — "success" | "error"

