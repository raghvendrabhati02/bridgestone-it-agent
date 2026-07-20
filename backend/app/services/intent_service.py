import logging
from app.services.llm_service import generate_response

logger = logging.getLogger("it-agent-backend")

# All valid IT issue categories — both diagnosable (multi-turn AI) and privileged (KB workflow)
_VALID_CATEGORIES = {
    # Core (original)
    "VPN", "PASSWORD_RESET", "OUTLOOK", "SOFTWARE_INSTALLATION",
    "PRINTER", "SAP", "NETWORK", "GENERAL",
    # Expanded diagnosable categories
    "TEAMS", "ONEDRIVE", "WIFI", "BROWSER", "ADOBE", "CITRIX",
    "BITLOCKER", "DRIVERS", "PERFORMANCE", "LOGIN",
    "WINDOWS", "OFFICE", "HARDWARE",
}


def detect_intent(message: str) -> str:
    """
    Detects the intent/category of the user message using Gemini AI.
    Falls back to keyword-based classification if Gemini is unavailable.
    """
    logger.info("Detecting intent for message using Gemini: %s", message)

    prompt = (
        "Analyze the following IT support query and classify it into exactly one of these categories:\n"
        "VPN, PASSWORD_RESET, OUTLOOK, SOFTWARE_INSTALLATION, PRINTER, SAP, NETWORK,\n"
        "TEAMS, ONEDRIVE, WIFI, BROWSER, ADOBE, CITRIX, BITLOCKER, DRIVERS, PERFORMANCE,\n"
        "LOGIN, WINDOWS, OFFICE, HARDWARE, GENERAL\n\n"
        f"Query: \"{message}\"\n\n"
        "Output ONLY the category name as a single word, with no other text, punctuation, or explanation."
    )

    try:
        res = generate_response(prompt)
        if isinstance(res, dict) and "debug_error" in res:
            logger.warning(
                "Gemini intent classification returned error: %s. Using local fallback.",
                res.get("debug_error"),
            )
        else:
            category = res.strip().upper()
            # Clean any accidental quotes/backticks/markdown formatting
            category = category.replace("`", "").replace('"', "").replace("'", "").strip()
            if category in _VALID_CATEGORIES:
                logger.info("Gemini classified intent successfully: %s", category)
                return category
            else:
                logger.warning(
                    "Gemini classified query as unknown category: %s. Using local fallback.",
                    category,
                )
    except Exception as e:
        logger.error(
            "Error classifying intent with Gemini: %s. Using local fallback.", e, exc_info=True
        )

    # ── Local keyword-based fallback ─────────────────────────────────────────
    text = message.lower()

    # VPN
    if any(kw in text for kw in ["vpn not working", "remote access", "vpn", "anyconnect", "globalprotect", "cisco vpn"]):
        return "VPN"

    # Wi-Fi
    if any(kw in text for kw in ["wifi", "wi-fi", "wireless", "no internet", "internet not working"]):
        return "WIFI"

    # Network (wired / general)
    if any(kw in text for kw in ["network", "lan", "connectivity", "gateway", "ethernet", "dns"]):
        return "NETWORK"

    # Microsoft Teams
    if any(kw in text for kw in ["teams", "microsoft teams", "teams call", "teams meeting", "teams chat"]):
        return "TEAMS"

    # OneDrive
    if any(kw in text for kw in ["onedrive", "one drive", "sync", "sharepoint sync"]):
        return "ONEDRIVE"

    # Outlook / Email
    if any(kw in text for kw in ["outlook", "email", "mailbox", "exchange", "mail"]):
        return "OUTLOOK"

    # Office suite (Word, Excel, PowerPoint, etc.)
    if any(kw in text for kw in ["office", "word", "excel", "powerpoint", "microsoft 365", "m365", "activation"]):
        return "OFFICE"

    # Browser
    if any(kw in text for kw in ["chrome", "edge", "firefox", "browser", "internet explorer", "ie ", "webpage", "website"]):
        return "BROWSER"

    # Adobe
    if any(kw in text for kw in ["adobe", "acrobat", "creative cloud", "photoshop", "illustrator", "pdf"]):
        return "ADOBE"

    # Citrix
    if any(kw in text for kw in ["citrix", "workspace", "receiver", "virtual desktop", "vdi"]):
        return "CITRIX"

    # SAP
    if "sap" in text:
        return "SAP"

    # Software installation
    if any(kw in text for kw in [
        "software install", "application install", "install software", "install application",
        "cannot install", "unable to install", "installation", "setup",
    ]):
        return "SOFTWARE_INSTALLATION"

    # Printer
    if any(kw in text for kw in ["printer", "printing", "print", "scanner"]):
        return "PRINTER"

    # BitLocker
    if any(kw in text for kw in ["bitlocker", "bit locker", "recovery key", "encrypted drive"]):
        return "BITLOCKER"

    # Drivers
    if any(kw in text for kw in ["driver", "device manager", "update driver", "install driver"]):
        return "DRIVERS"

    # Performance
    if any(kw in text for kw in [
        "slow", "sluggish", "lagging", "freezing", "frozen", "hang", "unresponsive",
        "high cpu", "high memory", "task manager", "performance",
    ]):
        return "PERFORMANCE"

    # Windows / BSOD
    if any(kw in text for kw in [
        "windows", "blue screen", "bsod", "update failed", "windows error",
        "system crash", "windows update",
    ]):
        return "WINDOWS"

    # Hardware
    if any(kw in text for kw in [
        "keyboard", "mouse", "monitor", "screen", "docking station", "webcam",
        "headset", "usb", "peripheral", "hardware",
    ]):
        return "HARDWARE"

    # Login / Authentication
    if any(kw in text for kw in ["login", "log in", "sign in", "cannot login", "mfa", "two factor", "authenticator"]):
        return "LOGIN"

    # Password
    if any(kw in text for kw in ["password", "reset password", "forgot password", "account locked"]):
        return "PASSWORD_RESET"

    return "GENERAL"