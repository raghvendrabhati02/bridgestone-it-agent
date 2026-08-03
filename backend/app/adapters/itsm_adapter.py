"""
itsm_adapter.py
─────────────────────────────────────────────────────────────────────────────
Abstract Base Adapter for ITSM Platform Integrations.
Standardizes ticket creation, updates, querying, and lifecycle operations across
backends (Mock ITSM, ServiceNow, Jira, Freshservice, Zendesk, etc.).
"""

from abc import abstractmethod
from typing import Dict, Any, List, Optional
from app.adapters.base_adapter import BaseAdapter


class ITSMAdapter(BaseAdapter):
    @abstractmethod
    def create_incident(
        self,
        category: str,
        description: str,
        assignment_group: Optional[str] = None,
        short_description: Optional[str] = None,
        caller_id: Optional[str] = None,
        priority: Optional[str] = None,
        **kwargs
    ) -> dict:
        """Creates an incident ticket."""
        pass

    @abstractmethod
    def get_incident(self, sys_id: str) -> dict:
        """Retrieves an incident by ticket number or sys_id."""
        pass

    @abstractmethod
    def update_incident(self, sys_id: str, updates: dict) -> dict:
        """Updates an incident by ticket number or sys_id."""
        pass

    @abstractmethod
    def close_incident(self, sys_id: str, resolution_notes: Optional[str] = None) -> dict:
        """Closes an incident."""
        pass

    @abstractmethod
    def get_all_incidents(self) -> list:
        """Retrieves all incidents."""
        pass

    @abstractmethod
    def create_service_request(
        self,
        category: str,
        description: str,
        action_type: Optional[str] = None,
        **kwargs
    ) -> dict:
        """Creates a service request."""
        pass

    @abstractmethod
    def get_request(self, sys_id: str) -> dict:
        """Retrieves a service request by ID."""
        pass

    @abstractmethod
    def update_request(self, sys_id: str, updates: dict) -> dict:
        """Updates a service request."""
        pass

    @abstractmethod
    def get_all_requests(self) -> list:
        """Retrieves all service requests."""
        pass
