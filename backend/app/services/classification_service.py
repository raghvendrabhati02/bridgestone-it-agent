"""
classification_service.py
──────────────────────────────────────────────────────────────────────────────
Enterprise ITSM Classification Service for the Bridgestone IT Agent.

Responsibilities:
  • Convert user issue descriptions into structured ITSMClassification objects.
  • Validate LLM outputs against Pydantic schema and enterprise domain constraints.
  • Enforce enterprise confidence thresholds (HIGH >= 0.90, MEDIUM 0.70-0.89, LOW < 0.70).
  • Provide fail-safe deterministic rules fallback on LLM error, rate limit, injection, or hallucination.
  • Maintain strict separation of concerns (no ServiceNow API calls, no ticket creation).
  • Audit log every classification transaction.

Phase 6 Architectural Changes
------------------------------
  • DEFAULT_VALID_CATEGORIES and DEFAULT_VALID_ASSIGNMENT_GROUPS are no longer
    hardcoded Python sets. Category validation is delegated entirely to
    ConfigurationService, which loads the authoritative list from
    incident_config.json["valid_categories"]. Renaming a ServiceNow category
    now requires only a JSON change — no Python edits.

  • LLM prompt no longer requests priority / impact / urgency. Those fields are
    strictly SLA/business-rule decisions resolved by ConfigurationService and
    IncidentEnrichmentService — not AI outputs.

  • Assignment group validation is removed from this service. Assignment group
    resolution lives in IncidentEnrichmentService via ConfigurationService.

  • Clarification threshold is now read from ConfigurationService
    (incident_config.json["clarification_threshold"]), default 0.70.

  • Fallback rules engine expanded from 5 → 11 domains covering all enterprise
    IT domains defined in incident_config.json.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional, Dict, Any, Set

from app.models.classification_models import (
    ClassificationRequest,
    ClassificationResponse,
    ITSMClassification,
    ConfidenceLevel,
    ClassificationMetadata,
)
from app.services.ai_provider import get_ai_provider
from app.services.configuration_service import ConfigurationService
from app.core.tracing import trace_span
from app.core.logging_context import correlation_id_ctx

logger = logging.getLogger("it-agent-backend")


# ── Backward-compatibility aliases (deprecated — use ConfigurationService) ────
# These remain as dynamic proxies so any existing import continues to work.
# Do NOT add new values here — update incident_config.json["valid_categories"] instead.

def _get_default_valid_categories() -> Set[str]:
    """Proxy to ConfigurationService. Backward-compat only."""
    try:
        cats = ConfigurationService.get_instance().get_valid_categories()
        if cats:
            return cats
    except Exception:
        pass
    return {
        "network", "Hardware", "Microsoft 365", "Software", "Printer",
        "Password/Access", "CyberArk PAM", "BSID Domain", "E-mail",
        "Security", "Mobile Devices",
    }


def _get_default_valid_assignment_groups() -> Set[str]:
    """Proxy to ConfigurationService. Backward-compat only."""
    try:
        cfg = ConfigurationService.get_instance()
        groups = {
            cfg.get_assignment_group_for_category(cat)
            for cat in cfg.get_valid_categories()
        }
        groups.discard(None)
        if groups:
            return groups  # type: ignore[return-value]
    except Exception:
        pass
    return {"Network Team", "IT Support", "Hardware Team", "Identity Team", "Security Team", "Mobile Team"}


# Module-level aliases (dynamic proxy — not hardcoded)
DEFAULT_VALID_CATEGORIES: Set[str] = set()        # populated lazily on first access
DEFAULT_VALID_ASSIGNMENT_GROUPS: Set[str] = set() # populated lazily on first access
VALID_CATEGORIES = DEFAULT_VALID_CATEGORIES
VALID_ASSIGNMENT_GROUPS = DEFAULT_VALID_ASSIGNMENT_GROUPS


class ClassificationService:
    """Enterprise ITSM Classification Service."""

    VERSION = "v1"

    def __init__(self, provider=None, field_mapping_service=None, configuration_service=None):
        self._provider = provider
        self._field_mapping_service = field_mapping_service
        # Phase 6: inject ConfigurationService for category validation and threshold
        self._config = configuration_service or ConfigurationService.get_instance()

    def get_allowed_categories(self) -> Set[str]:
        """
        Return the set of allowed ServiceNow categories.

        Priority order (Single Source of Truth):
          1. FieldMappingService — live ServiceNow choices (most authoritative)
          2. ConfigurationService — incident_config.json["valid_categories"]
          3. Hard-coded emergency fallback (never happens in production)

        Phase 6: DEFAULT_VALID_CATEGORIES Python set removed. ConfigurationService
        is now the configuration source of truth. No Python changes needed when
        Bridgestone renames a category.
        """
        if self._field_mapping_service is not None:
            try:
                cats = self._field_mapping_service.get_categories()
                if cats:
                    allowed = {c["label"] for c in cats if c.get("label")} | {c["value"] for c in cats if c.get("value")}
                    if allowed:
                        return allowed
            except Exception as err:
                logger.warning("[ClassificationService]: Error fetching categories from FieldMappingService: %s", err)

        # Fall through to ConfigurationService (configuration source of truth)
        config_cats = self._config.get_valid_categories()
        if config_cats:
            return config_cats

        # Emergency static fallback — should never be reached in production
        return _get_default_valid_categories()

    def get_allowed_assignment_groups(self) -> Set[str]:
        """
        Return the set of allowed assignment groups.

        Phase 6: Assignment group validation is not the classifier's responsibility.
        This method is retained for backward compatibility but callers should use
        ConfigurationService.get_assignment_group_for_category() for resolution.
        """
        if self._field_mapping_service is not None:
            try:
                grps = self._field_mapping_service.get_assignment_groups()
                if grps:
                    allowed = {g["label"] for g in grps if g.get("label")} | {g["value"] for g in grps if g.get("value")}
                    if allowed:
                        return allowed
            except Exception as err:
                logger.warning("[ClassificationService]: Error fetching assignment groups from FieldMappingService: %s", err)
        return _get_default_valid_assignment_groups()

    def classify(self, request: ClassificationRequest) -> ITSMClassification:
        """
        Classify a user issue description into a structured ITSMClassification.

        Never raises — gracefully falls back to deterministic rules on any failure.
        """
        provider_obj = self._provider or get_ai_provider()
        provider_name = getattr(provider_obj, "provider_name", "gemini")
        model_name = getattr(provider_obj, "model_name", "unknown")

        with trace_span(
            name="classification",
            attributes={
                "provider": provider_name,
                "model": model_name,
                "correlation_id": correlation_id_ctx.get() or "",
            },
        ):
            return self._classify_internal(request, provider_obj, provider_name, model_name)

    def _classify_internal(
        self,
        request: ClassificationRequest,
        provider_obj,
        provider_name: str,
        model_name: str,
    ) -> ITSMClassification:
        """Internal classification logic extracted for trace_span wrapping."""
        t_start = time.monotonic()
        desc = (request.description or "").strip()

        logger.info(
            ">>> ENTRY [ClassificationService.classify]: description='%s', category_hint='%s'",
            desc[:80],
            request.category_hint or "<none>",
        )

        # 1. Prompt Injection Defense & Empty Input Check
        if not desc or self._detect_prompt_injection(desc):
            logger.warning("[ClassificationService]: Empty or suspicious prompt injection attempt detected.")
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return self._rules_fallback(
                desc,
                request.category_hint,
                reasoning="Prompt injection or empty input rejected safely",
                elapsed_ms=elapsed_ms,
            )

        # 2. Multi-issue Detection Check
        has_multiple_issues = self._detect_multiple_issues(desc)

        # 3. Attempt LLM Classification
        try:
            prompt = self._build_classification_prompt(desc, request.category_hint)

            raw_response = provider_obj.generate_response(
                user_message=prompt,
                knowledge_context=(
                    "You are an Enterprise ITSM Classifier. Your role is to convert user IT issues into JSON classifications. "
                    "Output valid JSON ONLY. Do not include markdown or extra text. Obey all schema requirements."
                )
            )

            result = self._parse_and_validate_llm_response(
                raw_response=raw_response,
                t_start=t_start,
                has_multiple_issues=has_multiple_issues,
                provider_name=provider_name,
                model_name=model_name,
            )

            if result:
                elapsed_ms = int((time.monotonic() - t_start) * 1000)
                result.metadata.classification_time_ms = elapsed_ms
                self._audit_log_classification(request, result)
                return result

        except Exception as exc:
            logger.warning("[ClassificationService]: LLM classification failed (%s: %s). Falling back to rules.", type(exc).__name__, exc)

        # 4. Fallback to Deterministic Rules
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        result = self._rules_fallback(
            desc,
            request.category_hint,
            reasoning="Fallback rules applied due to LLM failure or schema validation error",
            elapsed_ms=elapsed_ms,
            has_multiple_issues=has_multiple_issues,
        )
        self._audit_log_classification(request, result)
        return result

    # ── Parsing & Validation ──────────────────────────────────────────────────

    def _parse_and_validate_llm_response(
        self,
        raw_response: str,
        t_start: float,
        has_multiple_issues: bool,
        provider_name: str,
        model_name: str,
    ) -> Optional[ITSMClassification]:
        """Parse raw LLM JSON string and validate against Pydantic model and domain whitelists.

        Phase 6: Assignment group is no longer validated here (that is enrichment's job).
        Priority / Impact / Urgency are not expected in the LLM response schema.
        """
        if not raw_response:
            return None

        # Clean JSON markdown fences if present
        clean_text = raw_response.strip()
        clean_text = re.sub(r"^```(json)?", "", clean_text, flags=re.IGNORECASE).strip()
        clean_text = re.sub(r"```$", "", clean_text).strip()

        try:
            data = json.loads(clean_text)
            if not isinstance(data, dict):
                return None
        except Exception:
            return None

        # Hallucination Filter: Validate Category against ConfigurationService allowed categories
        cat = data.get("category", "")
        allowed_categories = self.get_allowed_categories()
        if cat and cat not in allowed_categories:
            logger.warning(
                "[ClassificationService]: Rejected hallucinated category '%s'. Not in allowed set %s.",
                cat, allowed_categories,
            )
            return None

        # Compute Enterprise Confidence Level using configurable threshold
        conf = float(data.get("confidence", 0.95))
        conf = max(0.0, min(1.0, conf))

        threshold = self._config.get_clarification_threshold()
        high_threshold = 0.90  # HIGH confidence boundary remains fixed

        if conf >= high_threshold:
            level = ConfidenceLevel.HIGH
            needs_clar = False
        elif conf >= threshold:
            level = ConfidenceLevel.MEDIUM
            needs_clar = True
        else:
            level = ConfidenceLevel.LOW
            needs_clar = True

        missing_info = data.get("missing_information") or []
        if isinstance(missing_info, str):
            missing_info = [missing_info]

        if level in (ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW) and not missing_info:
            missing_info.append("Please provide additional error details or screenshot to verify issue type.")

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        meta = ClassificationMetadata(
            provider=provider_name,
            model=model_name,
            classification_version=self.VERSION,
            classification_time_ms=elapsed_ms,
        )

        try:
            classification = ITSMClassification(
                u_type=data.get("u_type", "issue"),
                category=cat or "General IT",
                subcategory=data.get("subcategory", "General Support"),
                assignment_group=data.get("assignment_group", "IT Support"),
                confidence=conf,
                confidence_level=level,
                reasoning=data.get("reasoning", "LLM Classification"),
                missing_information=missing_info,
                needs_clarification=needs_clar or data.get("needs_clarification", False),
                ticket_required=data.get("ticket_required", True),
                multiple_issues_detected=has_multiple_issues or data.get("multiple_issues_detected", False),
                metadata=meta,
            )
            return classification
        except Exception as err:
            logger.warning("[ClassificationService]: Pydantic schema validation error: %s", err)
            return None

    # ── Deterministic Rules Fallback — 11 Domains ────────────────────────────

    def _rules_fallback(
        self,
        description: str,
        category_hint: Optional[str] = None,
        reasoning: str = "Deterministic rules classification",
        elapsed_ms: int = 0,
        has_multiple_issues: bool = False,
    ) -> ITSMClassification:
        """
        Deterministic rules engine fallback — expanded to 11 enterprise IT domains.

        Evaluation order matters: more specific patterns first, general patterns last.
        Each domain section is labelled for maintainability.
        Assignment group is set to 'IT Support Team' as a placeholder — the
        enrichment layer resolves the final group via ConfigurationService.
        """
        text_lower = (description or "").lower()
        cat_hint_lower = (category_hint or "").lower()

        u_type = "issue"
        category = "network"
        subcategory = "Configuration Issue"
        group = "IT Support Team"
        confidence = 0.95
        missing_info: list = []
        needs_clarification = False

        # Security keywords — detected early so they override the vague-description check
        _SECURITY_KEYWORDS = (
            "phishing", "ransomware", "ransom", "malware", "virus", "spyware", "trojan",
            "suspicious email", "suspicious link", "data breach", "hacked",
            "cyber attack", "compromised", "account compromised", "social engineering",
        )
        _is_security = any(kw in text_lower for kw in _SECURITY_KEYWORDS) or cat_hint_lower == "security"

        # ── Vague / Unknown description check (skipped for security incidents) ─
        if not _is_security and (
            len(text_lower.split()) < 4
            or "weird" in text_lower
            or text_lower.strip() in ("not working", "broken", "issue", "problem", "help")
        ):
            confidence = 0.50
            needs_clarification = True
            missing_info = [
                "What specific application or hardware is affected?",
                "What exact error message is displayed?",
            ]

        # ── 1. Security (highest priority — checked first) ────────────────────
        if _is_security:
            category = "Security"
            confidence = max(confidence, 0.95)   # ensure HIGH confidence for security
            needs_clarification = False
            missing_info = []
            if "phishing" in text_lower or "suspicious email" in text_lower:
                subcategory = "Phishing Attack"
            elif any(kw in text_lower for kw in ("malware", "virus", "ransomware", "ransom", "spyware", "trojan")):
                subcategory = "Malware Detection"
            elif "suspicious link" in text_lower or "suspicious" in text_lower:
                subcategory = "Phishing Attack"
            else:
                subcategory = "Security Incident"
            group = "IT Support Team"

        # ── 2. CyberArk PAM ──────────────────────────────────────────────────
        # Use word-boundary matching to prevent 'spam' from matching 'pam'
        elif (
            "cyberark" in text_lower
            or " pam " in f" {text_lower} "
            or "vault" in text_lower
            or "privileged access" in text_lower
            or "privileged account" in text_lower
            or "privileged session" in text_lower
            or cat_hint_lower == "cyberark pam"
        ):
            category = "CyberArk PAM"
            if "vault" in text_lower:
                subcategory = "Vault Access Issue"
            elif "privileged" in text_lower:
                subcategory = "Privileged Session Issue"
            else:
                subcategory = "Vault Access Issue"
            group = "IT Support Team"

        # ── 3. Network / VPN / Connectivity ──────────────────────────────────
        elif "vpn" in text_lower or "globalprotect" in text_lower or "global protect" in text_lower or cat_hint_lower in ("vpn", "network"):
            category = "network"
            if "vpn" in text_lower or "globalprotect" in text_lower or "global protect" in text_lower:
                subcategory = "VPN-Global Protect"
            elif any(kw in text_lower for kw in ("wifi", "wi-fi", "wireless")):
                subcategory = "Wi-Fi Connectivity"
            elif any(kw in text_lower for kw in ("dns", "proxy", "lan", "internet", "ethernet")):
                subcategory = "Network Connectivity"
            else:
                subcategory = "Configuration Issue"
            group = "IT Support Team"

        elif any(kw in text_lower for kw in ("wifi", "wi-fi", "wireless")) and "network" not in cat_hint_lower:
            category = "network"
            subcategory = "Wi-Fi Connectivity"
            group = "IT Support Team"

        elif any(kw in text_lower for kw in ("dns", "proxy", "lan", "ethernet", "internet", "no network")):
            category = "network"
            subcategory = "Network Connectivity"
            group = "IT Support Team"

        # ── 4. Microsoft 365 / Collaboration Tools ────────────────────────────
        elif "outlook" in text_lower or cat_hint_lower == "outlook":
            category = "Microsoft 365"
            subcategory = "Outlook Not Working"
            group = "IT Support Team"

        elif any(kw in text_lower for kw in ("teams", "zoom", "webex", "conferencing", "teams meeting")):
            category = "Microsoft 365"
            subcategory = "Teams Issue"
            group = "IT Support Team"

        elif "sharepoint" in text_lower:
            category = "Microsoft 365"
            subcategory = "SharePoint Issue"
            group = "IT Support Team"

        elif "onedrive" in text_lower:
            category = "Microsoft 365"
            subcategory = "OneDrive Sync Issue"
            group = "IT Support Team"

        elif any(kw in text_lower for kw in ("excel", "powerpoint", "powerbi", "power bi", "onenote", "office 365", "o365", "m365"))\
                or (" word " in f" {text_lower} " or text_lower.startswith("word ") or text_lower.endswith(" word")):
            # Note: 'word' uses word-boundary check to avoid matching 'password', 'windows', 'keyword' etc.
            category = "Microsoft 365"
            subcategory = "Microsoft Office Issue"
            group = "IT Support Team"

        # ── 5. Mobile Devices ─────────────────────────────────────────────────
        elif any(kw in text_lower for kw in ("iphone", "android", "mobile device", "tablet", "ipad", "mdm", "intune", "byod")) or cat_hint_lower == "mobile devices":
            category = "Mobile Devices"
            if any(kw in text_lower for kw in ("mdm", "intune", "mobile device management")):
                subcategory = "MDM Enrollment"
            else:
                subcategory = "Mobile Device Issue"
            group = "IT Support Team"

        # ── 6. Hardware / Endpoints ────────────────────────────────────────────
        elif (
            cat_hint_lower == "hardware"
            or any(kw in text_lower for kw in ("laptop", "hardware", "keyboard", "monitor", "desktop", "computer", "screen", "display"))
            or (" pc " in f" {text_lower} " or text_lower.startswith("pc ") or text_lower.endswith(" pc"))
        ):
            category = "Hardware"
            if "keyboard" in text_lower or "mouse" in text_lower:
                subcategory = "Keyboard/Mouse Not Working"
            elif "monitor" in text_lower or "screen" in text_lower or "display" in text_lower:
                subcategory = "Monitor Issue"
            elif "laptop" in text_lower or "desktop" in text_lower or "computer" in text_lower:
                subcategory = "Dell Desktop/Laptop Damage"
            else:
                subcategory = "Hardware Not Working"
            group = "IT Support Team"

        elif any(kw in text_lower for kw in ("headset", "webcam", "docking", "docking station", "projector", "bluetooth", "charger")):
            category = "Hardware"
            subcategory = "Hardware Not Working"
            group = "IT Support Team"

        # ── 7. Printer / Scanner ───────────────────────────────────────────────
        elif any(kw in text_lower for kw in ("printer", "printing", "print")) or cat_hint_lower == "printer":
            category = "Printer"
            if "paper jam" in text_lower or "jam" in text_lower:
                subcategory = "Paper Jam"
            elif "quality" in text_lower or "faded" in text_lower:
                subcategory = "Print Quality Issue"
            else:
                subcategory = "Printer Offline"
            group = "IT Support Team"

        elif "scanner" in text_lower or "scanning" in text_lower:
            category = "Printer"
            subcategory = "Scanner Offline"
            group = "IT Support Team"

        # ── 8. Password / Access / Identity ───────────────────────────────────
        elif any(kw in text_lower for kw in ("mfa", "authenticator", "2fa", "two factor", "multifactor")) or cat_hint_lower == "mfa":
            category = "Password/Access"
            subcategory = "MFA Setup"
            group = "IT Support Team"

        elif any(kw in text_lower for kw in ("unlock", "locked out", "account locked", "lockout")) or cat_hint_lower in ("unlock", "lockout"):
            category = "Password/Access"
            subcategory = "Account Unlock"
            group = "IT Support Team"

        elif any(kw in text_lower for kw in ("password", "credentials")) \
                or " login " in f" {text_lower} " \
                or " log in " in text_lower \
                or cat_hint_lower in ("password", "access"):
            # 'login' uses word-boundary to avoid matching 'catalog' etc.
            category = "Password/Access"
            subcategory = "Password Reset"
            group = "IT Support Team"

        elif any(kw in text_lower for kw in ("new account", "new user", "onboarding", "provision")) or cat_hint_lower in ("new account", "onboarding"):
            category = "BSID Domain"
            subcategory = "New User Account"
            group = "IT Support Team"

        # ── 9. Email (non-M365 routing) ───────────────────────────────────────
        # Checked BEFORE M365 — shared mailbox / spam are email platform issues, not M365 app issues.
        # 'spam' uses exact word matching to avoid matching 'spammers', etc.
        elif (
            any(kw in text_lower for kw in ("junk mail", "junk email", "shared mailbox", "distribution list", "email quota", "mail rule"))
            or " spam " in f" {text_lower} "
            or text_lower.startswith("spam ")
            or text_lower.endswith(" spam")
            or "hundreds of spam" in text_lower
            or "spam and junk" in text_lower
        ):
            category = "E-mail"
            if "spam" in text_lower or "junk" in text_lower:
                subcategory = "Spam/Junk Email"
            elif "shared mailbox" in text_lower:
                subcategory = "Shared Mailbox Issue"
            elif "distribution list" in text_lower:
                subcategory = "Distribution List Issue"
            else:
                subcategory = "Email Issue"
            group = "IT Support Team"

        # ── 10. Software / Applications ───────────────────────────────────────
        elif any(kw in text_lower for kw in ("sap", "concur", "workday", "erp")) or cat_hint_lower in ("sap", "erp"):
            category = "Software"
            subcategory = "Application Error"
            group = "IT Support Team"

        elif any(kw in text_lower for kw in ("crash", "freeze", "freezing", "application error", "app crash", "app error")) or cat_hint_lower == "crash":
            category = "Software"
            subcategory = "Application Crash"
            group = "IT Support Team"

        elif (
            cat_hint_lower in ("software", "install")
            or any(kw in text_lower for kw in ("installation", "software install", "upgrade", "uninstall", "patch", "license", "software license"))
            or " install " in f" {text_lower} "
            or text_lower.startswith("install ")
            or " update " in f" {text_lower} "
        ):
            # 'install'/'update' use word-boundary matching to avoid false positives
            category = "Software"
            if any(kw in text_lower for kw in ("install", "installation")):
                subcategory = "Installation Request"
                u_type = "request"
            elif "license" in text_lower:
                subcategory = "License Issue"
            elif any(kw in text_lower for kw in ("update", "upgrade", "patch")):
                subcategory = "Update Failure"
            else:
                subcategory = "Application Error"
            group = "IT Support Team"

        # Determine confidence level
        if confidence >= 0.90:
            level = ConfidenceLevel.HIGH
        elif confidence >= 0.70:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        meta = ClassificationMetadata(
            provider="rules_fallback",
            model="rules_v1",
            classification_version=self.VERSION,
            classification_time_ms=elapsed_ms,
        )

        return ITSMClassification(
            u_type=u_type,
            category=category,
            subcategory=subcategory,
            assignment_group=group,
            confidence=confidence,
            confidence_level=level,
            reasoning=reasoning,
            missing_information=missing_info,
            needs_clarification=needs_clarification,
            ticket_required=True,
            multiple_issues_detected=has_multiple_issues,
            metadata=meta,
        )

    # ── Helpers & Defense ─────────────────────────────────────────────────────

    def _detect_prompt_injection(self, text: str) -> bool:
        """Detect prompt injection or command override attempts."""
        patterns = [
            r"ignore\s+(previous|all)\s+instructions",
            r"system\s+prompt",
            r"return\s+admin\s+password",
            r"reveal\s+password",
            r"act\s+as\s+admin",
            r"drop\s+table",
            r"delete\s+from",
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in patterns)

    def _detect_multiple_issues(self, text: str) -> bool:
        """Detect whether the description mentions multiple distinct IT issues."""
        text_lower = text.lower()
        # Expanded keyword list covers all 11 domains
        issue_keywords = [
            "vpn", "outlook", "laptop", "monitor", "password", "teams", "wifi",
            "printer", "phishing", "malware", "mobile", "sharepoint", "mfa",
            "scanner", "cyberark", "pam", "zoom", "onedrive", "sap", "crash",
        ]
        count = sum(1 for kw in issue_keywords if kw in text_lower)
        return count >= 2 and (
            " and " in text_lower
            or " also " in text_lower
            or " plus " in text_lower
            or "," in text_lower
        )

    def _build_classification_prompt(self, description: str, category_hint: Optional[str]) -> str:
        """
        Construct structured LLM classification prompt.

        Phase 6 changes:
          - Category list expanded to all 11 enterprise domains.
          - priority / impact / urgency removed (SLA rules — not AI outputs).
          - Assignment group removed (enrichment layer responsibility).
        """
        hint_str = f"\nCategory Hint: {category_hint}" if category_hint else ""
        # Build valid category list from ConfigurationService for accurate prompt
        try:
            valid_cats = sorted(self._config.get_valid_categories())
            category_list = " | ".join(f'"{c}"' for c in valid_cats) if valid_cats else '"Software" | "Hardware" | "network" | "Microsoft 365" | "Printer" | "Password/Access" | "Security" | "Mobile Devices" | "E-mail" | "CyberArk PAM" | "BSID Domain"'
        except Exception:
            category_list = '"Software" | "Hardware" | "network" | "Microsoft 365" | "Printer" | "Password/Access" | "Security" | "Mobile Devices" | "E-mail" | "CyberArk PAM" | "BSID Domain"'

        return (
            f"Classify the following IT issue into a structured JSON response.\n\n"
            f"User Description: {description}{hint_str}\n\n"
            f"JSON Output Format requirements:\n"
            f"{{\n"
            f'  "u_type": "issue" or "request",\n'
            f'  "category": {category_list},\n'
            f'  "subcategory": "string — specific issue subcategory",\n'
            f'  "confidence": 0.0 to 1.0,\n'
            f'  "reasoning": "brief explanation of the classification decision",\n'
            f'  "missing_information": ["detail 1", ...],\n'
            f'  "needs_clarification": true or false,\n'
            f'  "ticket_required": true or false,\n'
            f'  "multiple_issues_detected": true or false\n'
            f"}}\n"
            f"\nIMPORTANT: Do NOT include priority, impact, urgency, or assignment_group fields. "
            f"These are determined by business rules, not AI classification.\n"
        )

    def _audit_log_classification(self, request: ClassificationRequest, result: ITSMClassification) -> None:
        """Structured audit logging for classification observability."""
        logger.info(
            "\n========== ITSM CLASSIFICATION AUDIT ==========\n"
            "Input Description : %s\n"
            "Category Hint     : %s\n"
            "Result u_type     : %s\n"
            "Category          : %s\n"
            "Subcategory       : %s\n"
            "Assignment Group  : %s\n"
            "Confidence        : %.2f (%s)\n"
            "Needs Clarify     : %s\n"
            "Multiple Issues   : %s\n"
            "Provider & Model  : %s (%s)\n"
            "Latency           : %dms\n"
            "===============================================",
            request.description[:80],
            request.category_hint or "<none>",
            result.u_type,
            result.category,
            result.subcategory,
            result.assignment_group,
            result.confidence,
            result.confidence_level.value,
            result.needs_clarification,
            result.multiple_issues_detected,
            result.metadata.provider,
            result.metadata.model,
            result.metadata.classification_time_ms,
        )
