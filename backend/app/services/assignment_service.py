def get_assignment_team(category: str) -> str:
    """
    Returns the designated IT support team name based on the category of the issue.
    """
    cat_upper = category.strip().upper()
    if cat_upper in ("VPN", "NETWORK"):
        return "Network Team"
    elif cat_upper in ("OUTLOOK", "TEAMS", "MICROSOFT_365"):
        return "Microsoft 365 Team"
    elif cat_upper in ("SOFTWARE_INSTALLATION", "SOFTWARE"):
        return "Software Support"
    elif cat_upper in ("PRINTER", "HARDWARE"):
        return "Hardware Support"
    elif cat_upper in ("SECURITY", "ACCESS_CONTROL"):
        return "Security Team"
    elif cat_upper in ("PASSWORD_RESET", "GENERAL", "SERVICE_DESK"):
        return "Service Desk"
    else:
        return "Service Desk"

def assign_team(category: str) -> dict:
    """
    Assignment Agent: Assigns the correct team based on the ticket category.
    Returns: {"assigned_team": "Team Name"}
    """
    team = get_assignment_team(category)
    return {"assigned_team": team}
