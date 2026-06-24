import logging
from app.services.llm_service import generate_response

logger = logging.getLogger("it-agent-backend")

def detect_intent(message: str) -> str:
    """
    Detects the intent/category of the user message using Gemini AI.
    """
    logger.info("Detecting intent for message using Gemini: %s", message)
    
    prompt = (
        "Analyze the following IT support query and classify it into exactly one of these categories:\n"
        "VPN, PASSWORD_RESET, OUTLOOK, SOFTWARE_INSTALLATION, PRINTER, SAP, NETWORK, GENERAL\n\n"
        f"Query: \"{message}\"\n\n"
        "Output ONLY the category name as a single word, with no other text, punctuation, or explanation."
    )
    
    try:
        res = generate_response(prompt)
        if isinstance(res, dict) and "debug_error" in res:
            logger.warning("Gemini intent classification returned error: %s. Using local fallback.", res.get("debug_error"))
        else:
            category = res.strip().upper()
            # Clean any accidental quotes/backticks/markdown formatting from the response
            category = category.replace('`', '').replace('"', '').replace("'", "").strip()
            
            valid_categories = {"VPN", "PASSWORD_RESET", "OUTLOOK", "SOFTWARE_INSTALLATION", "PRINTER", "SAP", "NETWORK", "GENERAL"}
            if category in valid_categories:
                logger.info("Gemini classified intent successfully: %s", category)
                return category
            else:
                logger.warning("Gemini classified query as unknown category: %s. Using local fallback.", category)
    except Exception as e:
        logger.error("Error classifying intent with Gemini: %s. Using local fallback.", e, exc_info=True)

    # Local keyword-based fallback logic
    text = message.lower()

    if any(kw in text for kw in ["vpn not working", "remote access", "vpn", "anyconnect"]):
        return "VPN"

    if any(kw in text for kw in ["wifi not connected", "wifi", "internet", "network", "lan", "connectivity", "gateway"]):
        return "NETWORK"

    if any(kw in text for kw in ["outlook", "email", "mailbox", "exchange"]):
        return "OUTLOOK"

    if any(kw in text for kw in ["software install", "application install", "install software", "install application", "cannot install", "unable to install", "installation", "setup"]):
        return "SOFTWARE_INSTALLATION"

    if "printer" in text:
        return "PRINTER"

    if "sap" in text:
        return "SAP"

    if "password" in text:
        return "PASSWORD_RESET"

    return "GENERAL"