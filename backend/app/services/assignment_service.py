def get_assignment_team(category: str) -> str:
    """
    Returns the designated IT support team name based on the category of the issue.
    """
    cat_upper = category.strip().upper()
    if cat_upper in ("VPN", "NETWORK"):
        return "Network Team"
    elif cat_upper == "OUTLOOK":
        return "Messaging Team"
    elif cat_upper in ("PASSWORD_RESET", "SOFTWARE_INSTALLATION", "PRINTER"):
        return "Desktop Support Team"
    elif cat_upper == "SAP":
        return "SAP Support Team"
    elif cat_upper == "GENERAL":
        return "IT Support Team"
    else:
        return "IT Support Team"

def assign_team(category: str) -> dict:
    """
    Assignment Agent: Assigns the correct team based on the ticket category.
    Returns: {"assigned_team": "Team Name"}
    """
    team = get_assignment_team(category)
    return {"assigned_team": team}
