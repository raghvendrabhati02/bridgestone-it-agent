def get_vpn_steps() -> list[str]:
    return [
        "Are you connected to the internet?",
        "What VPN client are you using?",
        "Do you see any error message?",
        "Have you restarted the VPN client?"
    ]

def get_outlook_steps() -> list[str]:
    return [
        "Can you send emails?",
        "Can you receive emails?",
        "Have you restarted Outlook?"
    ]

def get_software_steps() -> list[str]:
    return [
        "Which software are you trying to install?",
        "Do you have administrator access?",
        "What error message do you see?"
    ]

def get_printer_steps() -> list[str]:
    return [
        "Is the printer powered on?",
        "Can other users print?",
        "Do you see any printer errors?"
    ]

def get_troubleshooting_steps(category: str) -> list[str]:
    category_upper = category.upper()
    if category_upper == "VPN":
        return get_vpn_steps()
    elif category_upper == "OUTLOOK":
        return get_outlook_steps()
    elif category_upper == "SOFTWARE_INSTALLATION":
        return get_software_steps()
    elif category_upper == "PRINTER":
        return get_printer_steps()
    return []
