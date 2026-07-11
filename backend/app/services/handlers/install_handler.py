"""
handlers/install_handler.py
─────────────────────────────────────────────────────────────────────────────
Handles tool: INSTALL_SOFTWARE

Routes to: action_service.create_software_install_request()
"""

from app.services.handlers import ok

TOOL = "INSTALL_SOFTWARE"


def handle(params: dict) -> dict:
    """→ action_service.create_software_install_request()"""
    from app.services.action_service import create_software_install_request
    software = params.get("software", "")
    result = create_software_install_request(software_name=software)
    return ok(TOOL, data=result, message=f"Software install request created for '{software}'.")
