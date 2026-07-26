"""
classification_models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data models and schemas for the Enterprise ClassificationService.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"      # >= 0.90 — Automatic classification
    MEDIUM = "MEDIUM"  # 0.70 - 0.89 — Suggest classification, ask 1 clarification
    LOW = "LOW"        # < 0.70 — Do not classify, needs clarification


class ClassificationMetadata(BaseModel):
    provider: str = Field(default="rules_fallback", description="LLM provider or fallback mechanism used")
    model: str = Field(default="none", description="Model identifier used for classification")
    classification_version: str = Field(default="v1", description="Schema/Service version")
    classification_time_ms: int = Field(default=0, description="Processing latency in milliseconds")


class ClassificationRequest(BaseModel):
    description: str = Field(..., min_length=1, description="User issue description or chat text")
    category_hint: Optional[str] = Field(default=None, description="Optional category hint if identified earlier")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional session/conversation metadata")


class ITSMClassification(BaseModel):
    u_type: str = Field(default="issue", description="ITSM request type ('issue' for Incident, 'request' for Service Request)")
    category: str = Field(default="General IT", description="Standard enterprise IT category")
    subcategory: str = Field(default="General Support", description="Standard enterprise IT subcategory")
    assignment_group: str = Field(default="IT Support", description="Assigned enterprise support team/group")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Classification confidence score between 0.0 and 1.0")
    confidence_level: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH, description="Enterprise confidence bracket")
    reasoning: str = Field(default="", description="Rationale explaining the classification")
    missing_information: List[str] = Field(default_factory=list, description="Key missing details if description is incomplete")
    needs_clarification: bool = Field(default=False, description="True if confidence is low or information is missing")
    ticket_required: bool = Field(default=True, description="True if issue requires ticket creation")
    multiple_issues_detected: bool = Field(default=False, description="True if multiple distinct issues were described")
    metadata: ClassificationMetadata = Field(default_factory=ClassificationMetadata, description="Observability metadata")


    @field_validator("confidence_level", mode="before")
    @classmethod
    def compute_confidence_level(cls, v: Any, info) -> ConfidenceLevel:
        if isinstance(v, ConfidenceLevel):
            return v
        if isinstance(v, str):
            try:
                return ConfidenceLevel(v.upper())
            except ValueError:
                pass
        # Derive level from numerical confidence score if available
        confidence_val = info.data.get("confidence", 1.0) if info.data else 1.0
        if confidence_val >= 0.90:
            return ConfidenceLevel.HIGH
        elif confidence_val >= 0.70:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    @field_validator("u_type")
    @classmethod
    def validate_u_type(cls, v: str) -> str:
        val = v.lower().strip()
        if val in ("incident", "inc", "issue"):
            return "issue"
        elif val in ("service_request", "sr", "request"):
            return "request"
        return "issue"


# Alias for backward compatibility / API consistency
ClassificationResponse = ITSMClassification



# Alias for backward/future API compatibility
ClassificationResponse = ITSMClassification
