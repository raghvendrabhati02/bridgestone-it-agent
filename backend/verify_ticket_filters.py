# verify_ticket_filters.py
# Verification test for ServiceNow Incident Queue Filtering logic.

def simulate_frontend_filter(ticket, filters):
    # 1. Search query
    if filters.get("searchQuery"):
        q = filters["searchQuery"].lower()
        matches = (
            q in ticket.get("ticket_id", "").lower() or
            q in ticket.get("category", "").lower() or
            q in ticket.get("assigned_team", "").lower() or
            q in ticket.get("status", "").lower() or
            q in ticket.get("issue_description", "").lower() or
            (ticket.get("servicenow_id") and q in ticket["servicenow_id"].lower())
        )
        if not matches:
            return False
            
    # 2. Status
    if filters.get("filterStatus") and ticket.get("status") != filters["filterStatus"]:
        return False
        
    # 3. Priority
    if filters.get("filterPriority") and ticket.get("priority") != filters["filterPriority"]:
        return False
        
    # 4. Category
    if filters.get("filterCategory") and ticket.get("category") != filters["filterCategory"]:
        return False
        
    # 5. Assigned Team
    if filters.get("filterGroup") and ticket.get("assigned_team") != filters["filterGroup"]:
        return False
        
    # 6. Assigned Engineer
    if filters.get("filterEngineer") and ticket.get("assigned_engineer") != filters["filterEngineer"]:
        return False
        
    # 7. SLA Status
    if filters.get("filterSla"):
        s = ticket.get("sla_state", "").upper()
        if filters["filterSla"] == "BREACHED" and s != "BREACHED":
            return False
        if filters["filterSla"] == "WARNING" and s not in ("WARNING_75", "WARNING_90"):
            return False
        if filters["filterSla"] == "HEALTHY" and s not in ("HEALTHY", ""):
            return False

    # 8. Created Date
    if filters.get("filterCreatedDate"):
        if not ticket.get("created_at") or not ticket["created_at"].startswith(filters["filterCreatedDate"]):
            return False
            
    return True

def test_ticket_filters():
    print("Running verify_ticket_filters...")
    
    mock_tickets = [
        {
            "ticket_id": "TKT-001",
            "category": "VPN",
            "issue_description": "Cannot connect to APAC gateway",
            "assigned_team": "Network",
            "status": "OPEN",
            "priority": "CRITICAL",
            "servicenow_id": "INC0001",
            "sla_state": "WARNING_90",
            "assigned_engineer": "Robert Chen (NetOps)",
            "created_at": "2026-06-29T08:00:00Z"
        },
        {
            "ticket_id": "TKT-002",
            "category": "Outlook",
            "issue_description": "Outlook keeps asking for password",
            "assigned_team": "Helpdesk",
            "status": "IN_PROGRESS",
            "priority": "MEDIUM",
            "servicenow_id": "INC0002",
            "sla_state": "HEALTHY",
            "assigned_engineer": "Emily Watson (Helpdesk L2)",
            "created_at": "2026-06-28T09:30:00Z"
        },
        {
            "ticket_id": "TKT-003",
            "category": "SAP",
            "issue_description": "SAP GUI lock on PRD",
            "assigned_team": "Sysadmin",
            "status": "RESOLVED",
            "priority": "HIGH",
            "servicenow_id": "INC0003",
            "sla_state": "BREACHED",
            "assigned_engineer": "Marcus Aurelius (SysOps)",
            "created_at": "2026-06-27T10:15:00Z"
        }
    ]

    # Test 1: Search query match
    res = [t for t in mock_tickets if simulate_frontend_filter(t, {"searchQuery": "APAC"})]
    assert len(res) == 1 and res[0]["ticket_id"] == "TKT-001"

    # Test 2: Status match
    res = [t for t in mock_tickets if simulate_frontend_filter(t, {"filterStatus": "RESOLVED"})]
    assert len(res) == 1 and res[0]["ticket_id"] == "TKT-003"

    # Test 3: Priority match
    res = [t for t in mock_tickets if simulate_frontend_filter(t, {"filterPriority": "HIGH"})]
    assert len(res) == 1 and res[0]["ticket_id"] == "TKT-003"

    # Test 4: Category match
    res = [t for t in mock_tickets if simulate_frontend_filter(t, {"filterCategory": "VPN"})]
    assert len(res) == 1 and res[0]["ticket_id"] == "TKT-001"

    # Test 5: Team match
    res = [t for t in mock_tickets if simulate_frontend_filter(t, {"filterGroup": "Helpdesk"})]
    assert len(res) == 1 and res[0]["ticket_id"] == "TKT-002"

    # Test 6: SLA warning match
    res = [t for t in mock_tickets if simulate_frontend_filter(t, {"filterSla": "WARNING"})]
    assert len(res) == 1 and res[0]["ticket_id"] == "TKT-001"

    # Test 7: SLA breached match
    res = [t for t in mock_tickets if simulate_frontend_filter(t, {"filterSla": "BREACHED"})]
    assert len(res) == 1 and res[0]["ticket_id"] == "TKT-003"

    # Test 8: Created Date match
    res = [t for t in mock_tickets if simulate_frontend_filter(t, {"filterCreatedDate": "2026-06-28"})]
    assert len(res) == 1 and res[0]["ticket_id"] == "TKT-002"

    # Test 9: Compound filters
    res = [t for t in mock_tickets if simulate_frontend_filter(t, {"filterCategory": "VPN", "filterPriority": "CRITICAL"})]
    assert len(res) == 1 and res[0]["ticket_id"] == "TKT-001"

    print("[PASS] verify_ticket_filters.py: client-side filter simulation passed successfully!")

if __name__ == "__main__":
    test_ticket_filters()
