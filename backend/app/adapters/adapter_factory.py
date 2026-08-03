"""
adapter_factory.py
─────────────────────────────────────────────────────────────────────────────
Factory pattern to retrieve active ITSMAdapter.
Controlled by environment variable:
  ITSM_PROVIDER = "mock" | "servicenow" | "jira" | "zendesk" (default: "mock")
"""

import os
import logging
import threading
from app.adapters.itsm_adapter import ITSMAdapter

logger = logging.getLogger("it-agent-backend")

_itsm_adapter_instance: ITSMAdapter = None
_adapter_lock = threading.Lock()


def get_itsm_adapter() -> ITSMAdapter:
    """
    Returns the thread-safe singleton instance of active ITSMAdapter based on ITSM_PROVIDER env.
    """
    global _itsm_adapter_instance
    if _itsm_adapter_instance is None:
        with _adapter_lock:
            if _itsm_adapter_instance is None:
                provider = os.getenv("ITSM_PROVIDER", "mock").lower()
                if provider == "servicenow":
                    from app.adapters.servicenow_adapter import ServiceNowAdapter
                    _itsm_adapter_instance = ServiceNowAdapter()
                    logger.info("ITSMAdapterFactory: Instantiated ServiceNowAdapter.")
                else:
                    from app.adapters.mock_itsm_adapter import MockITSMAdapter
                    _itsm_adapter_instance = MockITSMAdapter()
                    logger.info("ITSMAdapterFactory: Instantiated MockITSMAdapter.")
    return _itsm_adapter_instance


def set_itsm_adapter(adapter: ITSMAdapter) -> None:
    """Injects a custom ITSMAdapter instance (useful for testing or runtime toggle)."""
    global _itsm_adapter_instance
    with _adapter_lock:
        _itsm_adapter_instance = adapter
        logger.info("ITSMAdapterFactory: Overrode active ITSMAdapter instance.")
