# User Guide – Bridgestone IT Agent

> **Version:** 1.0.0 | **Last updated:** 2026-07-11

This guide covers how employees, managers, and administrators use the Bridgestone IT Agent platform.

---

## 1. Getting Started

### 1.1 Accessing the Platform

Open your browser and navigate to:
- **Development:** `http://localhost:3000`
- **Production:** Your company's IT portal URL (provided by your IT team)

### 1.2 Logging In

1. Enter your **username** and **password**
2. Click **Sign In**
3. You will be taken to the dashboard appropriate for your role

**Default test accounts:**

| Username | Role | Password |
|----------|------|----------|
| `employee` | Employee | `employeepassword` |
| `manager` | Manager | `managerpassword` |
| `admin` | Admin | `adminpassword` |

> These are development-only accounts. Contact your IT administrator for your production credentials.

---

## 2. Employee Portal

### 2.1 AI Support Chat

The AI Support Chat is the primary way employees get IT help. You can describe your problem in plain language.

**How to use:**

1. Click **AI Support** in the left sidebar
2. Type your problem in the chat box
3. The AI will guide you through troubleshooting steps
4. Follow each step and confirm if it resolved your issue

**Supported issue types:**

| Issue | Example messages |
|-------|-----------------|
| VPN | "My VPN is not working", "Can't connect to VPN" |
| Outlook / Email | "Outlook won't open", "Emails not syncing" |
| Printer | "Printer offline", "Print queue stuck" |
| Software | "Install Zoom for me", "Chrome not loading" |
| Network / WiFi | "No internet connection", "WiFi is slow" |
| Password | "Reset my password", "Account locked out" |
| SAP | "SAP login failing", "SAP transaction error" |

**Chat commands:**

| Command | What it does |
|---------|-------------|
| "create ticket" | Creates a support ticket immediately |
| "restart" | Starts a new conversation |
| "cancel" | Cancels the current session |
| "check my ticket status" | Shows the status of your most recent ticket |
| "yes" / "no" | Confirms or declines a troubleshooting step |
| "issue resolved" / "working now" | Marks your issue as resolved |

---

### 2.2 Troubleshooting Flow

The AI follows a structured troubleshooting process:

```
1. You describe your problem
2. AI identifies the issue category (VPN, Outlook, etc.)
3. AI searches the Knowledge Base for relevant steps
4. AI guides you through steps one at a time
5. You confirm each step (yes/no)
6. If resolved → session ends with a resolution acknowledgement
7. If not resolved after all steps → AI offers to create a support ticket
```

---

### 2.3 Creating a Support Ticket

If troubleshooting doesn't resolve your issue, the AI will offer to create a ticket.

1. Type "yes" when prompted, or type "create ticket" at any time
2. The AI creates a ticket automatically in ServiceNow
3. You receive a **Ticket ID** (e.g., `TKT-001`)
4. The ticket is routed to the appropriate IT team based on your issue category

**Ticket types:**

| Type | Examples | Approval needed? |
|------|----------|-----------------|
| **Incident** | VPN, Outlook, Printer issues | No |
| **Service Request** | Software installation, New laptop | Yes (Manager) |
| **Privileged Action** | VPN access restoration | Yes (Manager/Admin) |

---

### 2.4 My Tickets

View and track all your support tickets:

1. Click **My Tickets** in the sidebar
2. See ticket status, priority, and assigned team
3. Click a ticket to view full details, comments, and timeline

**Ticket statuses:**

| Status | Meaning |
|--------|---------|
| `NEW` | Just created, not yet assigned |
| `WAITING_MANAGER` | Pending manager approval |
| `ASSIGNED` | Assigned to an engineer |
| `IN_PROGRESS` | Engineer is actively working on it |
| `PENDING` | Waiting for your response |
| `RESOLVED` | Engineer marked it resolved |
| `CLOSED` | Ticket is complete |
| `REJECTED` | Request was rejected by manager |

---

### 2.5 Notifications

The bell icon in the top bar shows your notifications. Notifications are sent for:
- Ticket status changes
- SLA warnings
- Approval decisions
- Comments on your tickets

---

## 3. Manager Portal

### 3.1 Approval Queue

Managers review and approve or reject Service Requests and Privileged Actions from their team.

**How to access:**
1. Click **Manager Portal** in the left sidebar
2. See all pending requests under **Pending Approvals**

**How to approve:**
1. Click on a ticket to view details
2. Review the request description and priority
3. Click **Approve** or **Reject**
4. Add a comment (optional but recommended)

**What happens after approval:**
- Approved tickets move to the Admin ITSM queue for fulfillment
- The employee is notified of the decision
- Rejected tickets are closed with the manager's reason

---

### 3.2 Team Ticket View

Managers can view all tickets from their team:

1. Click **Team Requests** in the Manager Portal
2. Filter by status, priority, or category
3. Assign tickets to specific engineers if needed

---

### 3.3 VPN Access Restoration Approval

When an employee requests VPN access restoration (a privileged action):

1. The AI chat flags this as a `PRIVILEGED_ACTION`
2. The system creates a pending approval record
3. You will see it in your **Pending Approvals** queue
4. Review the request and approve or reject

> **Note:** Employees cannot approve privileged actions themselves. The system will display an `ACCESS_DENIED` message if an employee attempts to approve their own VPN restoration request.

---

## 4. Administrator Portal

### 4.1 ITSM Queue

The ITSM Queue is the full ticket management view for IT administrators.

**Capabilities:**
- View all tickets across all users
- Filter by status, category, priority, assignment group
- Assign tickets to engineers
- Update ticket lifecycle (approve, start, resolve, close)
- Add comments and notes

---

### 4.2 Knowledge Base Management

Administrators can create and manage knowledge base articles that the AI uses for troubleshooting.

**How to create an article:**
1. Go to **Knowledge Base** → **Admin** tab
2. Click **New Article**
3. Fill in: Title, Category, Problem description, Troubleshooting steps, Verification steps, Escalation policy
4. Click **Save as Draft**
5. Click **Publish** to make it available to the AI

**Article structure:**

| Section | Purpose |
|---------|---------|
| Title | Short, descriptive name |
| Category | Matches IT issue category (VPN, OUTLOOK, etc.) |
| Keywords | Words that trigger this article |
| Problem | What the article addresses |
| Symptoms | How the problem manifests |
| Troubleshooting Steps | Step-by-step resolution instructions |
| Verification | How to confirm the issue is resolved |
| Escalation | What to do if steps fail |

---

### 4.3 Analytics Dashboard

The analytics dashboard provides IT performance metrics:

- **Ticket volume** – Total tickets over time
- **Resolution time** – Average time to resolve by category
- **SLA compliance** – Percentage of tickets resolved within SLA
- **Category breakdown** – Distribution of issue types
- **AI resolution rate** – Percentage of issues resolved without ticket creation

---

### 4.4 Device Management

View and manage enterprise devices:

1. Click **Devices** in the sidebar
2. See device inventory: hostname, IP, OS, status, assigned user
3. Filter by department, status, or assigned user
4. View device health information from the device agent

---

### 4.5 Scheduler / Jobs

Manage background automation jobs:

1. Click **Execution Center** in the sidebar
2. View all scheduled jobs and their last/next run times
3. Enable or disable individual jobs
4. Trigger a job manually for immediate execution
5. Review execution history

**Available jobs:**

| Job | Default frequency | Purpose |
|-----|------------------|---------|
| SLA Monitor | Every 60 seconds | Checks SLA status on all open tickets |
| Auto-Close | Configurable | Closes resolved tickets after idle period |
| Cleanup | Configurable | Removes stale session data |
| Notifications | Configurable | Sends pending notification records |

---

### 4.6 Audit Logs

All administrator actions are audited. Access via:
- **Audit Logs** – General action audit trail
- **Security Logs** – Authentication and access events
- **RBAC Audit Logs** – Permission checks and denials
- **Agent Traces** – AI reasoning traces per session

---

## 5. Service Catalog

The Service Catalog allows employees to submit structured requests for IT services.

**How to submit a request:**
1. Go to the **Service Catalog** section
2. Browse available services (Software, Hardware, Access, etc.)
3. Select the service you need
4. Fill in the request details
5. Submit

**Request workflow:**
1. Request is submitted → status: `SUBMITTED`
2. Manager receives notification → reviews in Manager Portal
3. Manager approves → status: `APPROVED` → moves to Admin queue
4. Admin fulfills → status: `FULFILLED`

---

## 6. SLA (Service Level Agreement)

### SLA Targets by Priority

| Priority | SLA (hours) | Assigned team |
|----------|-------------|--------------|
| CRITICAL | 2 | IT Security / Network |
| HIGH | 4 | Level 2 Support |
| MEDIUM | 8 | Level 1 Support |
| LOW | 24 | Service Desk |

### SLA Warnings

You and your manager will receive notifications at these thresholds:

| Notification | When |
|-------------|------|
| Warning (75%) | 75% of SLA time consumed |
| Warning (90%) | 90% of SLA time consumed |
| Breach | SLA deadline passed |
| Escalation L1 | Immediately on breach |
| Escalation L2 | 30 minutes after breach |
| Escalation L3 | 60 minutes after breach |

---

## 7. Tips and Best Practices

### For Employees

- **Be specific** when describing your problem: Include error messages, what you were doing, and when it started.
- **Follow all steps** – The AI's troubleshooting steps are ordered for maximum effectiveness. Don't skip steps.
- **Check your ticket status** – Use "check my ticket status" in the chat to get an update.
- **Rate your experience** – After resolution, submit a satisfaction score to help improve the service.

### For Managers

- **Review approvals promptly** – Service Requests and Privileged Actions may be time-sensitive. Check your Pending Approvals daily.
- **Add comments when rejecting** – This helps employees understand why and what to do next.

### For Administrators

- **Keep the Knowledge Base updated** – The AI's effectiveness depends on current, accurate KB articles.
- **Monitor SLA compliance** – Check the Analytics Dashboard weekly to identify trends and staffing needs.
- **Review security logs** – Periodically review failed login attempts and permission denials for security incidents.
