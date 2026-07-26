"""
troubleshooting_strategy.py
──────────────────────────────────────────────────────────────────────────────
Enterprise Troubleshooting Strategy Registry for the Bridgestone IT Agent.

A TroubleshootingStrategy is NOT a step-by-step script.

It defines:
  • what evidence matters for a domain
  • the natural troubleshooting sequence (guidance, not mandate)
  • stopping conditions (when to declare resolved or escalate)
  • escalation criteria
  • future policy notes (admin/LAPS — Phase 3)

The AI uses the strategy as a reasoning frame — it reasons *within* the
strategy rather than starting from scratch on every issue, giving consistency
without making the assistant robotic.

Phase 1 scope: INCIDENTS ONLY
  VPN, OUTLOOK, PRINTER, TEAMS, NETWORK, PASSWORD, SAP,
  HARDWARE, SOFTWARE, BROWSER, GENERAL (fallback)

Service Requests are out of scope until Phase 5.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("it-agent-backend")


# ── Data Contract ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TroubleshootingStrategy:
    """
    Immutable domain strategy that guides the ReasoningEngine.

    Fields
    ------
    name:               Human-readable strategy name.
    domain:             Uppercase canonical domain key (e.g. "VPN").
    required_evidence:  Information the AI should gather before choosing a path.
    common_sequence:    Typical troubleshooting order — guidance, not mandate.
    stopping_conditions: Conditions that indicate the issue is resolved.
    escalation_criteria: Conditions that should trigger a ServiceNow ticket.
    policy_notes:       Future admin/LAPS policy hints (Phase 3).
    """
    name: str
    domain: str
    required_evidence: List[str]
    common_sequence: List[str]
    stopping_conditions: List[str]
    escalation_criteria: List[str]
    policy_notes: List[str] = field(default_factory=list)


# ── Registry ──────────────────────────────────────────────────────────────────

class TroubleshootingStrategyRegistry:
    """
    In-memory registry of TroubleshootingStrategy instances.

    Provides domain-to-strategy lookup with a safe GENERAL fallback for
    any unrecognised category. New strategies can be registered at runtime.
    """

    FALLBACK_DOMAIN = "GENERAL"

    def __init__(self) -> None:
        self._strategies: Dict[str, TroubleshootingStrategy] = {}
        self._load_defaults()

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, domain: str) -> TroubleshootingStrategy:
        """
        Return strategy for the given domain.

        Normalises the key (uppercase, strip whitespace).
        Falls back to GENERAL if the domain is not registered.
        """
        key = (domain or "").upper().strip().replace(" ", "_").replace("/", "_")
        strategy = self._strategies.get(key)
        if strategy is None:
            logger.info(
                "[TroubleshootingStrategyRegistry]: No strategy for domain '%s' — using GENERAL fallback.",
                domain,
            )
            strategy = self._strategies[self.FALLBACK_DOMAIN]
        return strategy

    def register(self, strategy: TroubleshootingStrategy) -> None:
        """Register or overwrite a strategy for its domain key."""
        key = strategy.domain.upper().strip()
        self._strategies[key] = strategy
        logger.debug(
            "[TroubleshootingStrategyRegistry]: Registered strategy '%s' for domain '%s'.",
            strategy.name, key,
        )

    def list_domains(self) -> List[str]:
        """Return all registered domain keys, sorted alphabetically."""
        return sorted(self._strategies.keys())

    # ── Built-in Strategies ───────────────────────────────────────────────────

    def _load_defaults(self) -> None:
        """Load all Phase 1 incident strategies."""

        defaults: List[TroubleshootingStrategy] = [

            TroubleshootingStrategy(
                name="VPN Troubleshooting",
                domain="VPN",
                required_evidence=[
                    "VPN client error code or message",
                    "VPN client name and version (e.g. GlobalProtect 6.x)",
                    "Operating system and version",
                    "Last time VPN worked successfully",
                    "Network type: corporate office, home, public Wi-Fi",
                ],
                common_sequence=[
                    "Confirm VPN client version and error code",
                    "Check internet connectivity independent of VPN",
                    "Restart VPN client and retry connection",
                    "Check system date/time accuracy (certificate issues)",
                    "Clear VPN client cache / logs",
                    "Reinstall VPN client if above steps fail",
                    "Escalate if reinstall does not resolve",
                ],
                stopping_conditions=[
                    "User confirms VPN connection is established",
                    "User is able to access corporate resources",
                ],
                escalation_criteria=[
                    "VPN client reinstall does not resolve the issue",
                    "Error indicates server-side or certificate authority problem",
                    "User is unable to work remotely and no workaround available",
                    "Error code suggests account/policy issue requiring admin action",
                ],
                policy_notes=[
                    "GlobalProtect gateway credentials are managed by Identity Team",
                    "Admin credentials may be required to reinstall drivers — Phase 3",
                ],
            ),

            TroubleshootingStrategy(
                name="Outlook / Email Troubleshooting",
                domain="OUTLOOK",
                required_evidence=[
                    "Exact error message or error code",
                    "Outlook version (e.g. Outlook 365, 2019)",
                    "Mailbox mode: Cached Exchange Mode or Online Mode",
                    "Whether the issue is with send, receive, calendar, or opening",
                    "Active add-ins that may conflict",
                ],
                common_sequence=[
                    "Identify the specific Outlook error and mode",
                    "Start Outlook in Safe Mode to isolate add-in conflicts",
                    "Repair the Outlook profile",
                    "Clear Outlook cache (OST file)",
                    "Run Office Repair tool",
                    "Escalate if profile repair and Office Repair fail",
                ],
                stopping_conditions=[
                    "Outlook opens and email send/receive is functional",
                    "Calendar is accessible and syncing",
                ],
                escalation_criteria=[
                    "Office Repair does not resolve the issue",
                    "Mailbox is corrupted or inaccessible at the Exchange level",
                    "Issue is with shared mailbox permissions (requires admin)",
                ],
            ),

            TroubleshootingStrategy(
                name="Printer Troubleshooting",
                domain="PRINTER",
                required_evidence=[
                    "Printer name and model",
                    "Connection type: network printer or local USB",
                    "Print queue status (stuck jobs, offline status)",
                    "Error message on screen or printer display",
                    "Whether the issue is with all users or a specific user",
                ],
                common_sequence=[
                    "Check print queue for stuck jobs and clear if necessary",
                    "Verify printer online status in Windows Devices and Printers",
                    "Restart the Print Spooler service",
                    "Remove and re-add the printer with current drivers",
                    "Test with a different document or application",
                    "Escalate if driver reinstall does not resolve",
                ],
                stopping_conditions=[
                    "User confirms successful test print",
                    "Print queue is clear and printer shows online",
                ],
                escalation_criteria=[
                    "Network printer unreachable from all workstations (infrastructure issue)",
                    "Driver installation requires admin privileges",
                    "Hardware fault on the printer itself",
                ],
                policy_notes=[
                    "Driver installation on managed devices may require admin — Phase 3",
                ],
            ),

            TroubleshootingStrategy(
                name="Microsoft Teams Troubleshooting",
                domain="TEAMS",
                required_evidence=[
                    "Error message or Teams error code",
                    "Whether the issue is with meetings, calls, chat, or file sharing",
                    "Device: laptop internal mic/cam or external hardware",
                    "Teams version and whether web Teams also fails",
                    "Meeting-specific or general issue",
                ],
                common_sequence=[
                    "Identify whether it is audio, video, chat, or meeting join issue",
                    "Check device permissions for microphone and camera in Windows Settings",
                    "Clear Teams cache",
                    "Sign out and back in to Teams",
                    "Reinstall Teams if cache clear does not help",
                    "Test on Teams web version to isolate app vs service",
                ],
                stopping_conditions=[
                    "User can join meetings and communicate successfully",
                    "Audio and video functional",
                ],
                escalation_criteria=[
                    "Teams service-wide issue (check Microsoft 365 Service Health)",
                    "Reinstall does not resolve",
                    "License or policy assignment issue requires admin",
                ],
            ),

            TroubleshootingStrategy(
                name="Network / Wi-Fi Troubleshooting",
                domain="NETWORK",
                required_evidence=[
                    "SSID / network name being connected to",
                    "IP address currently assigned (or if APIPA 169.x.x.x)",
                    "Error: cannot connect, connected but no internet, or slow",
                    "Device type and OS version",
                    "Whether other devices on same network are affected",
                ],
                common_sequence=[
                    "Identify if the issue is connection or internet access",
                    "Check IP address (ipconfig) for valid DHCP assignment",
                    "Forget and reconnect to Wi-Fi network",
                    "Flush DNS and reset TCP/IP stack",
                    "Check network adapter driver version",
                    "Escalate if infrastructure-level (affects multiple users)",
                ],
                stopping_conditions=[
                    "User has valid IP and internet connectivity",
                    "Network resources are accessible",
                ],
                escalation_criteria=[
                    "Multiple users affected — likely network infrastructure issue",
                    "DHCP server or DNS not responding",
                    "Physical network equipment fault",
                ],
            ),

            TroubleshootingStrategy(
                name="Password / Account Access Troubleshooting",
                domain="PASSWORD",
                required_evidence=[
                    "Account type: Windows login, email, SAP, or other application",
                    "Error: password expired, account locked, or incorrect credentials",
                    "Whether self-service password reset (SSPR) portal is available",
                    "Last successful login date",
                ],
                common_sequence=[
                    "Confirm which account and system the user cannot access",
                    "Direct user to self-service password reset portal (SSPR) if available",
                    "If account locked: wait for auto-unlock period or escalate to IT",
                    "If SSPR fails: verify user identity and reset manually",
                    "Confirm user can log in after reset",
                ],
                stopping_conditions=[
                    "User successfully logs in with new credentials",
                    "Account is unlocked and accessible",
                ],
                escalation_criteria=[
                    "SSPR portal unavailable or user identity cannot be verified",
                    "Active Directory issue requiring domain admin",
                    "Security concern — possible account compromise",
                ],
                policy_notes=[
                    "Account unlock and manual reset may require Level 2 admin — Phase 3",
                ],
            ),

            TroubleshootingStrategy(
                name="SAP Troubleshooting",
                domain="SAP",
                required_evidence=[
                    "SAP transaction code or module (e.g. MM60, FI, HR)",
                    "Exact error message or short dump code",
                    "SAP GUI version",
                    "Whether the issue is login, transaction, or performance",
                    "Whether the issue is specific to this user or all users",
                ],
                common_sequence=[
                    "Identify the exact SAP error and affected transaction",
                    "Check SAP GUI version and update if outdated",
                    "Clear SAP GUI cache",
                    "Try alternate SAP logon server if available",
                    "Escalate to SAP Basis team if error is server-side",
                ],
                stopping_conditions=[
                    "User can log in and complete the affected transaction",
                ],
                escalation_criteria=[
                    "SAP short dumps requiring Basis-level analysis",
                    "Authorization/role assignment issues requiring SAP admin",
                    "Server-side performance or connection issue",
                ],
            ),

            TroubleshootingStrategy(
                name="Hardware Troubleshooting",
                domain="HARDWARE",
                required_evidence=[
                    "Device type: laptop, desktop, monitor, keyboard, mouse, docking station",
                    "Symptom: not powering on, display issue, keyboard/mouse unresponsive, overheating",
                    "BIOS version if relevant",
                    "Whether the issue appeared after a specific event (drop, update, move)",
                    "Whether peripheral or built-in component",
                ],
                common_sequence=[
                    "Identify the specific hardware component and symptom",
                    "Perform basic power cycle / reconnect",
                    "Update or roll back device drivers",
                    "Test with alternate hardware if available (e.g. different monitor)",
                    "Run hardware diagnostics if available",
                    "Escalate for physical inspection or replacement",
                ],
                stopping_conditions=[
                    "Hardware is functional after driver update or reconnect",
                    "Issue was peripheral — resolved by replacement or reconnect",
                ],
                escalation_criteria=[
                    "Physical hardware failure requiring replacement",
                    "Issue appeared after physical damage (drop, liquid)",
                    "BIOS-level or firmware issue",
                ],
            ),

            TroubleshootingStrategy(
                name="Software / Application Crash Troubleshooting",
                domain="SOFTWARE",
                required_evidence=[
                    "Application name and version",
                    "Exact error message or crash code",
                    "Whether the crash is on launch or during use",
                    "Recent Windows updates or software changes before issue started",
                    "Whether the issue is specific to one user or all users on device",
                ],
                common_sequence=[
                    "Identify the specific application and error",
                    "Check Windows Event Viewer for crash details",
                    "Run application as administrator to rule out permission issue",
                    "Repair or reinstall the application",
                    "Roll back recent Windows updates if crash coincides with update",
                    "Escalate if reinstall fails or crash is system-level",
                ],
                stopping_conditions=[
                    "Application launches and runs without crashing",
                ],
                escalation_criteria=[
                    "Reinstall does not resolve crash",
                    "Multiple applications crashing — possible OS-level issue",
                    "Crash related to missing system DLL or corrupted Windows files",
                ],
            ),

            TroubleshootingStrategy(
                name="Browser Troubleshooting",
                domain="BROWSER",
                required_evidence=[
                    "Browser name and version (Chrome, Edge, Firefox)",
                    "Whether all sites are affected or specific sites/applications",
                    "Installed extensions that may conflict",
                    "Whether private/incognito mode reproduces the issue",
                    "Error code or message shown",
                ],
                common_sequence=[
                    "Reproduce issue in incognito/private mode (rules out extensions)",
                    "Clear browser cache and cookies",
                    "Disable extensions one by one to isolate",
                    "Reset browser to default settings",
                    "Try alternate browser to confirm if browser-specific",
                    "Escalate if issue is with a corporate web application",
                ],
                stopping_conditions=[
                    "Website or application loads successfully",
                    "Issue confirmed as external (third-party site outage)",
                ],
                escalation_criteria=[
                    "Corporate web application inaccessible — application team involvement needed",
                    "Certificate or proxy policy issue requiring network admin",
                ],
            ),

            TroubleshootingStrategy(
                name="General IT Troubleshooting",
                domain="GENERAL",
                required_evidence=[
                    "Detailed description of the issue",
                    "Which application, system, or device is affected",
                    "When the issue started and whether anything changed",
                    "Steps the user has already tried",
                    "Whether the issue is recurring or one-time",
                ],
                common_sequence=[
                    "Gather complete issue description",
                    "Reproduce the issue if possible",
                    "Apply most likely basic fix (restart, reinstall, re-login)",
                    "Search for related KB article",
                    "Escalate if basic remediation does not resolve",
                ],
                stopping_conditions=[
                    "User confirms the issue is resolved",
                ],
                escalation_criteria=[
                    "Issue persists after reasonable troubleshooting attempts",
                    "Category identified that requires domain-specific specialist",
                    "Security or data integrity concern",
                ],
            ),
        ]

        # Category aliases for flexible domain lookup
        aliases: Dict[str, str] = {
            "GUEST_WIFI": "NETWORK",
            "WIFI": "NETWORK",
            "WI_FI": "NETWORK",
            "PASSWORD_RESET": "PASSWORD",
            "DEVICE_HEALTH": "HARDWARE",
            "SOFTWARE_INSTALLATION": "SOFTWARE",
            "SOFTWARE_CRASH": "SOFTWARE",
            "MICROSOFT_TEAMS": "TEAMS",
            "GENERAL_IT": "GENERAL",
            "PASSWORD_ACCESS": "PASSWORD",
        }

        for strategy in defaults:
            self._strategies[strategy.domain.upper()] = strategy

        # Register aliases pointing to the canonical strategy
        for alias, canonical in aliases.items():
            if canonical in self._strategies:
                self._strategies[alias] = self._strategies[canonical]

        logger.info(
            "[TroubleshootingStrategyRegistry]: Loaded %d strategies for domains: %s",
            len(defaults),
            [s.domain for s in defaults],
        )
