import os
import logging

logger = logging.getLogger("it-agent-backend")

# Base directory for the knowledge base (c:\Projects\it-agent\knowledge_base)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "knowledge_base"))

# Map of categories to guide directories and file names
GUIDE_MAPPING = {
    "VPN": ("vpn", "vpn_guide.txt"),
    "OUTLOOK": ("outlook", "outlook_guide.txt"),
    "SOFTWARE_INSTALLATION": ("software_installation", "software_installation_guide.txt"),
    "PASSWORD_RESET": ("password_reset", "password_reset_guide.txt"),
    "PRINTER": ("printer", "printer_guide.txt")
}

def get_guide_content(category: str) -> tuple[str, str]:
    """
    Generic loader to read guide contents from the knowledge base directory.
    Returns a tuple of (content, filename).
    """
    category_upper = category.upper()
    if category_upper not in GUIDE_MAPPING:
        logger.warning("Knowledge Service: Requested category has no guide defined: %s", category)
        return (f"No specific guide found for category: {category}. Please contact IT support.", "N/A")
    
    subfolder, filename = GUIDE_MAPPING[category_upper]
    file_path = os.path.join(BASE_DIR, subfolder, filename)
    
    if not os.path.exists(file_path):
        logger.error("Knowledge Service: File not found at %s", file_path)
        return (f"Error: The troubleshooting guide file '{filename}' was not found.", filename)
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            logger.warning("Knowledge Service: File at %s is empty", file_path)
            return (f"Notice: The troubleshooting guide for {category} is empty.", filename)
        return content, filename
    except Exception as e:
        logger.error("Knowledge Service: Error reading file at %s: %s", file_path, e)
        return (f"Error: Failed to read from the guide file '{filename}'.", filename)

def get_vpn_guide() -> tuple[str, str]:
    return get_guide_content("VPN")

def get_outlook_guide() -> tuple[str, str]:
    return get_guide_content("OUTLOOK")

def get_software_installation_guide() -> tuple[str, str]:
    return get_guide_content("SOFTWARE_INSTALLATION")

def get_password_reset_guide() -> tuple[str, str]:
    return get_guide_content("PASSWORD_RESET")

def get_printer_guide() -> tuple[str, str]:
    return get_guide_content("PRINTER")
