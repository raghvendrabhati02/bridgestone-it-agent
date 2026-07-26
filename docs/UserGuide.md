# User Guide

> **Project:** Bridgestone IT AI Assistant · **Last updated:** 2026-07-26

---

## Getting Started

### Accessing the Platform

Open your browser and navigate to:
- **Development:** `http://localhost:3000`
- **Production:** Your company's IT portal URL

### Logging In

1. Enter your **username** and **password**
2. Click **Sign In**
3. You are taken to the dashboard for your role

**Development test accounts:**

| Username | Role | Password |
|---|---|---|
| `employee` | Employee | `employeepassword` |
| `manager` | Manager | `managerpassword` |
| `admin` | Admin | `adminpassword` |

---

## Employee Portal

### IT Support Chat

The IT Support Chat is the primary way employees get IT help.

1. Click **IT Support** in the sidebar
2. Describe your problem in plain language
3. The AI guides you through troubleshooting steps one at a time
4. Confirm each step with "yes" or "no"
5. If the issue is resolved, type "issue resolved" or "working now"
6. If unresolved, the AI creates a support ticket automatically

**Supported issue types:**

| Issue | Example messages |
|---|---|
| VPN | "My VPN is not working", "Can't connect to remote access" |
| Outlook / Email | "Outlook won't open", "Emails not syncing" |
| Printer | "Printer offline", "Print queue stuck" |
| Software installation | "Install VS Code", "I need Chrome installed" |
| Network / WiFi | "No internet connection", "WiFi is slow" |
| Password | "Reset my password", "Account locked out" |
| SAP | "SAP login failing", "SAP transaction error" |

**Useful chat commands:**

| Command | What it does |
|---|---|
| "create ticket" | Creates a support ticket immediately |
| "restart" | Starts a new conversation |
| "cancel" | Cancels the current session |
| "check my ticket status" | Shows the status of your most recent ticket |
| "issue resolved" / "working now" | Marks your issue as resolved |

---

### Software Installation Requests

If you request software that requires administrator rights (e.g. VS Code, SAP GUI, Zoom):

1. The AI recognises this as a privileged request
2. A service request ticket is created with status **Waiting for Manager Approval**
3. You receive a message: *"Your request has been raised and is awaiting manager approval."*
4. Once approved by your manager and fulfilled by the IT admin, you will see an **Enterprise Admin Access Card** in your chat with temporary credentials

> **Note:** The temporary administrator credentials shown are generated for demonstration purposes only and expire after 15 minutes.

---

### My Tickets

View and track all your support tickets:

1. Click **My Tickets** in the sidebar
2. See ticket status, priority, and assigned team

**Ticket statuses:**

| Status | Meaning |
|---|---|
| `NEW` | Just created, not yet assigned |
| `WAITING_MANAGER` | Pending your manager's approval |
| `READY_FOR_ADMIN` | Manager approved; IT admin will fulfil the request |
| `ACCESS_GRANTED` | IT admin has granted access |
| `COMPLETED` | Request completed |
| `ASSIGNED` | Assigned to an engineer |
| `IN_PROGRESS` | Engineer is actively working |
| `PENDING` | Waiting for your response |
| `RESOLVED` | Engineer marked it resolved |
| `CLOSED` | Ticket is complete |
| `REJECTED` | Request was rejected by your manager |

---

### Notifications

The bell icon in the top bar shows your notifications:
- Ticket status changes
- SLA warnings
- Approval decisions

---

## Manager Portal

### Pending Approvals

Managers review service requests from their team members.

1. Click **Manager Portal** in the sidebar
2. See all pending requests under **Pending Approvals**

**How to approve a request:**
1. Click **Inspect** on a pending ticket to view details
2. Review the request description, priority, and employee
3. Click **Approve** and optionally add notes
4. The ticket moves to the IT Admin Queue automatically
5. The employee is notified

**How to reject a request:**
1. Click **Inspect** on a pending ticket
2. Click **Reject** and add a reason
3. The ticket is marked as Rejected and the employee is notified

### Approved Requests

The **Approved Requests** tab shows all requests you have approved, with:
- Approval time
- Approval notes
- Current status

### Request History

View the complete approval history across all requests.

---

## IT Admin Portal (ITSM Queue)

### Dashboard

The Admin Console dashboard shows:
- Live ticket counts (New, Assigned, In Progress, Pending Today)
- Resolved and Closed today
- AI Resolution Rate
- Average Resolution Time
- Charts: Tickets by Category, Tickets by Team, Priority Levels

### Ticket Queue

1. Click **ITSM Queue** in the sidebar
2. View all tickets in the system
3. Filter by status, category, priority

**For approved privileged requests (status: `READY_FOR_ADMIN`):**

1. Click **Inspect** on the ticket
2. Click **Grant Temporary Admin Access**
3. The employee's chat view updates with the Enterprise Admin Access Card
4. Once the employee confirms installation, click **Mark Complete**

### Analytics

The **Analytics** view provides:
- **SLA Compliance Rate** — Trend chart against the 95% target
- **Volume Trend** — Ticket volume by day of week

### Knowledge Base

Administrators manage the articles the AI uses for troubleshooting:

1. Click **Knowledge Base** in the sidebar
2. Click **New Article** to create an article
3. Fill in: Title, Category, Problem, Troubleshooting Steps, Verification steps
4. Click **Save as Draft**, then **Publish** to make it available to the AI

**Article fields:**

| Field | Purpose |
|---|---|
| Title | Short, descriptive name |
| Category | Maps to IT issue category (VPN, OUTLOOK, etc.) |
| Keywords | Words that trigger this article |
| Problem | What the article addresses |
| Troubleshooting Steps | Step-by-step resolution instructions |
| Verification | How to confirm the issue is resolved |
| Escalation | What to do if steps fail |

---

## SLA Targets

| Priority | SLA (hours) |
|---|---|
| CRITICAL | 2 |
| HIGH | 4 |
| MEDIUM | 8 |
| LOW | 24 |

**SLA state notifications:**

| State | Notification |
|---|---|
| Warning (75%) | 75% of SLA time consumed — manager notified |
| Warning (90%) | 90% consumed — manager and admin notified |
| Breached | Deadline passed — all parties notified |
| Escalation L1 | Immediately on breach |
| Escalation L2 | 30 minutes after breach |
| Escalation L3 | 60 minutes after breach |

---

## Tips and Best Practices

### For Employees

- **Be specific:** Include error messages, what you were doing, and when the issue started.
- **Follow all steps:** The AI's troubleshooting steps are ordered for maximum effectiveness.
- **Check ticket status:** Use "check my ticket status" in the chat for an update.

### For Managers

- **Review approvals promptly:** Software installation requests may be time-sensitive.
- **Add notes when approving or rejecting:** Notes are recorded in the approval history and visible to the IT admin.

### For Administrators

- **Keep the Knowledge Base updated:** The AI's troubleshooting accuracy depends on current, accurate articles.
- **Monitor SLA compliance:** Check the Analytics dashboard to identify trends.
- **Review security logs:** Check failed login attempts and permission denials periodically.

---

## Related Documents

- [Architecture](./architecture.md) — System overview
- [AI Workflow](./ai-workflow.md) — How the AI pipeline works
- [Security](./Security.md) — Role permissions matrix
