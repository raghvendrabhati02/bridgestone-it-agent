"""
servicenow_payload_inspector.py
─────────────────────────────────────────────────────────────────────────────
Diagnostic service for verifying and auditing the ServiceNow integration.

Responsibilities:
  - Logs IncidentCreateRequest and raw REST JSON payload prior to POST.
  - Logs POST response returned by ServiceNow REST Table API.
  - Compares Generated Metadata → REST Payload → Stored ServiceNow Values.
  - Produces a clear, structured field-by-field diagnostic report:
    Generated Value → JSON Key → Value Sent → Value Stored → Reason if rejected.
  - Controlled by SERVICENOW_VALIDATE_MAPPING env var (default: True).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from app.models.servicenow_models import extract_sn_field

logger = logging.getLogger("it-agent-backend")


@dataclass
class FieldAuditResult:
    field_label: str
    generated_val: str
    json_key_sent: str
    servicenow_field: str
    value_sent: str
    value_stored: str
    status: str
    reason_if_rejected: str
    icon: str


class ServiceNowPayloadInspector:
    """Diagnostic inspector for verifying ServiceNow payload serialization and storage."""

    def __init__(self) -> None:
        raw_val = os.getenv("SERVICENOW_VALIDATE_MAPPING", "true").strip().lower()
        self.enabled: bool = raw_val in ("true", "1", "yes")

    def inspect_pre_post(
        self,
        request_summary: Dict[str, Any],
        final_payload: Dict[str, Any],
    ) -> None:
        """Log request details and final JSON payload immediately prior to REST POST."""
        try:
            payload_str = json.dumps(final_payload, indent=2)
        except Exception:
            payload_str = str(final_payload)

        logger.info(
            "\n================================================================================\n"
            "PRE-POST DEBUG: IncidentCreateRequest Summary:\n"
            "  short_description : %s\n"
            "  category          : %s\n"
            "  severity          : %s\n"
            "  assignment_group  : %s\n"
            "  caller_id         : %s\n"
            "  impact            : %s\n"
            "  urgency           : %s\n"
            "  priority          : %s\n"
            "  extra_fields      : %s\n"
            "--------------------------------------------------------------------------------\n"
            "PRE-POST DEBUG: Final JSON Payload Sent to ServiceNow REST API:\n"
            "%s\n"
            "================================================================================",
            request_summary.get("short_description"),
            request_summary.get("category"),
            request_summary.get("severity"),
            request_summary.get("assignment_group"),
            request_summary.get("caller_id"),
            request_summary.get("impact"),
            request_summary.get("urgency"),
            request_summary.get("priority"),
            request_summary.get("extra_fields"),
            payload_str,
        )

    def inspect_post_response(self, response_dict: Dict[str, Any]) -> None:
        """Log raw POST response returned by ServiceNow."""
        try:
            resp_str = json.dumps(response_dict, indent=2)
        except Exception:
            resp_str = str(response_dict)

        logger.info(
            "\n================================================================================\n"
            "POST RESPONSE: Response Returned by ServiceNow REST API:\n"
            "%s\n"
            "================================================================================",
            resp_str,
        )

    def verify_and_compare(
        self,
        generated_metadata: Dict[str, Any],
        payload_sent: Dict[str, Any],
        stored_values: Dict[str, Any],
    ) -> List[FieldAuditResult]:
        """
        Compare Generated Metadata → REST Payload → Stored ServiceNow Values.
        Outputs a 5-step report: Generated Value → JSON Key → Value Sent → Value Stored → Reason if rejected.
        """
        field_specs = [
            ("Short Description", "short_description", "short_description", "short_description"),
            ("Description",       "description",       "description",       "description"),
            ("Category",          "category",          "category",          "category"),
            ("Subcategory",       "subcategory",       "subcategory",       "subcategory"),
            ("Assignment Group",  "assignment_group",  "assignment_group",  "assignment_group"),
            ("Impact",            "impact",            "impact",            "impact"),
            ("Urgency",           "urgency",           "urgency",           "urgency"),
            ("Priority",          "priority",          "priority",          "priority"),
            ("Channel / Contact", "channel",           "contact_type",      "contact_type"),
            ("Incident Type",     "incident_type",     "u_type",            "u_type"),
            ("Config Item (CI)",  "configuration_item","cmdb_ci",           "cmdb_ci"),
            ("Business Service",  "business_service",  "business_service",  "business_service"),
            ("Location",          "location",          "location",          "location"),
        ]

        results: List[FieldAuditResult] = []

        for label, gen_key, json_key, sn_field in field_specs:
            gen_val = generated_metadata.get(gen_key)
            if gen_val is None and json_key in payload_sent:
                gen_val = payload_sent.get(json_key)

            sent_val = payload_sent.get(json_key)
            stored_val = extract_sn_field(stored_values, sn_field, default="")

            # Determine audit status and specific rejection reason if ignored
            if gen_val is None and sent_val is None:
                status = "NOT_PROVIDED"
                icon = "⚪"
                reason = "Field was not provided in request metadata."
            elif sent_val is not None:
                sent_str = str(sent_val).strip().lower()
                stored_str = str(stored_val).strip().lower()

                if stored_val and stored_val != "":
                    if sent_str in stored_str or stored_str in sent_str or sent_str == stored_str:
                        status = "MATCH"
                        icon = "✅"
                        reason = "N/A (Successfully stored)"
                    else:
                        status = "VALUE_MISMATCH"
                        icon = "⚠️"
                        reason = f"Stored value '{stored_val}' differs from sent value '{sent_val}' (dictionary label or transform)."
                else:
                    if json_key == "assignment_group":
                        status = "REFERENCE_LOOKUP_FAILED"
                        icon = "❌"
                        reason = "ServiceNow reference field requires 32-character sys_id. Display value created invalid reference URI."
                    elif json_key in ("cmdb_ci", "business_service", "location"):
                        status = "REFERENCE_LOOKUP_FAILED"
                        icon = "❌"
                        reason = "Reference field requires 32-character sys_id. Display name lookup failed or was rejected."
                    elif json_key in ("category", "subcategory"):
                        status = "FIELD_NOT_STORED"
                        icon = "❌"
                        reason = "ServiceNow sys_choice validation rejected value. Choice key must match configured sys_choice element."
                    elif json_key == "contact_type":
                        status = "FIELD_NOT_STORED"
                        icon = "❌"
                        reason = "ServiceNow contact_type choice validation rejected value. Must be lower_snake choice key (e.g. 'virtual_agent')."
                    else:
                        status = "FIELD_NOT_STORED"
                        icon = "❌"
                        reason = "Field was present in payload but ignored by ServiceNow (restricted ACL, inactive choice, or unmapped field)."
            else:
                status = "DROPPED_BEFORE_POST"
                icon = "❌"
                reason = "Field was dropped prior to REST POST."

            results.append(
                FieldAuditResult(
                    field_label=label,
                    generated_val=str(gen_val) if gen_val is not None else "(none)",
                    json_key_sent=json_key if sent_val is not None else "(not sent)",
                    servicenow_field=sn_field,
                    value_sent=str(sent_val) if sent_val is not None else "(not sent)",
                    value_stored=str(stored_val) if stored_val else "(blank)",
                    status=status,
                    reason_if_rejected=reason,
                    icon=icon,
                )
            )

        # Print structured 5-column diagnostic mapping report table to log
        logger.info(
            "\n========================================================================================================================\n"
            "SERVICENOW FIELD MAPPING DIAGNOSTIC REPORT\n"
            "========================================================================================================================\n"
            "%-18s | %-18s | %-18s | %-18s | %-18s | %s\n"
            "------------------------------------------------------------------------------------------------------------------------",
            "FIELD LABEL", "GENERATED VALUE", "JSON KEY", "VALUE SENT", "VALUE STORED", "STATUS & REASON IF REJECTED"
        )
        for r in results:
            logger.info(
                "%-18s | %-18s | %-18s | %-18s | %-18s | %s %s (%s)",
                r.field_label[:18],
                r.generated_val[:18],
                r.json_key_sent[:18],
                r.value_sent[:18],
                r.value_stored[:18],
                r.icon,
                r.status,
                r.reason_if_rejected,
            )
        logger.info("========================================================================================================================\n")

        return results
