"""
multi_agent_interface.py
──────────────────────────────────────────────────────────────────────────────
Sprint 10: Multi-Agent Extension Point & Interfaces (Version 2.0 Preparedness)

Defines abstract base classes, protocol interfaces, and coordinator extension
points for future Multi-Agent swarm & specialist agent orchestration.

NOTE: This module provides extension interfaces for future V2.X enhancements
without altering current LangGraph single/multi-node execution behavior.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseAgent(ABC):
    """Abstract Base Class for all autonomous sub-agents."""

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Unique identifier for the agent."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """List of functional capabilities handled by this agent."""
        pass

    @abstractmethod
    async def process_turn(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Processes a single conversational or task turn."""
        pass


class TriageAgentInterface(BaseAgent):
    """Extension interface for specialized intent classification & triage agents."""

    @property
    def agent_name(self) -> str:
        return "triage_agent"

    @property
    def capabilities(self) -> List[str]:
        return ["intent_classification", "category_prediction", "risk_screening"]

    async def process_turn(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extension point stub processing turn."""
        return state


class DiagnosticAgentInterface(BaseAgent):
    """Extension interface for automated diagnostic & RAG knowledge agents."""

    @property
    def agent_name(self) -> str:
        return "diagnostic_agent"

    @property
    def capabilities(self) -> List[str]:
        return ["knowledge_retrieval", "troubleshooting_step_generation", "root_cause_analysis"]

    async def process_turn(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extension point stub processing turn."""
        return state


class ActionAgentInterface(BaseAgent):
    """Extension interface for corrective action & system integration agents."""

    @property
    def agent_name(self) -> str:
        return "action_agent"

    @property
    def capabilities(self) -> List[str]:
        return ["servicenow_incident_creation", "laps_credential_issuance", "ad_group_management"]

    async def process_turn(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extension point stub processing turn."""
        return state



class MultiAgentCoordinatorInterface(ABC):
    """Abstract coordinator interface for orchestrating multi-agent collaboration."""

    @abstractmethod
    def register_agent(self, agent: BaseAgent) -> None:
        """Registers a specialist agent with the coordinator."""
        pass

    @abstractmethod
    async def route_and_execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Routes a incoming task to the appropriate specialist agent(s)."""
        pass
