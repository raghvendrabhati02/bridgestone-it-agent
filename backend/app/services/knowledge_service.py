"""
knowledge_service.py
─────────────────────────────────────────────────────────────────────────────
Knowledge Engine v2  —  Single source of truth for all KB operations.

Design principles
-----------------
• Auto-discovers every *.json file under backend/knowledge_base/
• Validates required fields on load; skips malformed articles gracefully
• Builds an inverted keyword index for O(1) candidate retrieval
• Weighted scoring: category (+5), title (+4), keyword (+3), symptom (+2),
  problem text (+2)
• Fuzzy alias matching so "vpn", "globalprotect", "remote access" all resolve
  to KB0002
• Read-only after startup — safe for FastAPI multi-threading
• Full backward compatibility with legacy get_guide_content(category) callers

Public API
----------
    load_articles()
    search(query)                  -> dict
    get_article(article_id)        -> Optional[dict]
    get_steps(article_id)          -> list[dict]
    get_step(article_id, step_number) -> Optional[dict]
    next_step(article_id, current_step) -> Optional[dict]
    previous_step(article_id, current_step) -> Optional[dict]
    get_verification(article_id)   -> list[str]
    get_escalation(article_id)     -> Optional[dict]
    get_screenshots(article_id)    -> list[dict]
    list_categories()              -> list[str]
    list_articles()                -> list[dict]

Legacy (backward compat)
------------------------
    get_guide_content(category)    -> tuple[str, str]
    search_by_category(category)   -> Optional[dict]
    get_troubleshooting_steps(article_id) -> list
    get_vpn_guide()
    get_outlook_guide()
    get_software_installation_guide()
    get_password_reset_guide()
    get_printer_guide()
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("it-agent-backend")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Path to the knowledge_base directory (relative to this module)
KB_DIR: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base")
)

# Required fields that every article must contain to be accepted
REQUIRED_FIELDS: Tuple[str, ...] = (
    "article_id",
    "title",
    "category",
    "keywords",
    "problem",
    "symptoms",
    "troubleshooting_steps",
    "verification",
    "escalation",
    "screenshots",
    "faq",
)

# Weighted scoring constants
SCORE_CATEGORY_MATCH:  float = 5.0
SCORE_TITLE_MATCH:     float = 4.0
SCORE_KEYWORD_MATCH:   float = 3.0
SCORE_SYMPTOM_MATCH:   float = 2.0
SCORE_PROBLEM_MATCH:   float = 2.0

# Normalised score ceiling used to convert raw score → confidence [0,1]
_SCORE_CEILING: float = 20.0

# Minimum confidence threshold before a result is considered a match
MIN_CONFIDENCE: float = 0.10

# Fuzzy alias table: query alias → canonical category string (upper-case)
_CATEGORY_ALIASES: Dict[str, str] = {
    # VPN
    "vpn": "VPN",
    "globalprotect": "VPN",
    "global protect": "VPN",
    "remote access": "VPN",
    "palo alto": "VPN",
    "vpn not connecting": "VPN",
    "work from home": "VPN",
    # PASSWORD
    "password": "PASSWORD_RESET",
    "reset password": "PASSWORD_RESET",
    "forgot password": "PASSWORD_RESET",
    "account locked": "PASSWORD_RESET",
    "unlock account": "PASSWORD_RESET",
    "active directory": "PASSWORD_RESET",
    # GUEST WIFI
    "wifi": "GUEST_WIFI",
    "guest wifi": "GUEST_WIFI",
    "wireless": "GUEST_WIFI",
    "bs-guest": "GUEST_WIFI",
    "bsguest": "GUEST_WIFI",
    # OUTLOOK
    "outlook": "OUTLOOK",
    "outlook not opening": "OUTLOOK",
    "email": "OUTLOOK",
    "exchange": "OUTLOOK",
    "mailbox": "OUTLOOK",
    # SHARED MAILBOX
    "shared mailbox": "SHARED_MAILBOX",
    "shared email": "SHARED_MAILBOX",
    "send as": "SHARED_MAILBOX",
    "shared calendar": "SHARED_MAILBOX",
    # PRINTER
    "printer": "PRINTER",
    "print": "PRINTER",
    "offline printer": "PRINTER",
    "paper jam": "PRINTER",
    "print queue": "PRINTER",
    # SOFTWARE
    "install software": "SOFTWARE_INSTALLATION",
    "software request": "SOFTWARE_INSTALLATION",
    "application": "SOFTWARE_INSTALLATION",
    "install": "SOFTWARE_INSTALLATION",
    "vs code": "SOFTWARE_INSTALLATION",
    # SAP
    "sap": "SAP",
    "sap login": "SAP",
    "sap gui": "SAP",
    "sap access": "SAP",
    # ASSET
    "laptop": "IT_ASSET_ALLOCATION",
    "hardware request": "IT_ASSET_ALLOCATION",
    "new laptop": "IT_ASSET_ALLOCATION",
    "asset allocation": "IT_ASSET_ALLOCATION",
    "joining kit": "IT_ASSET_ALLOCATION",
    # DEVICE HEALTH
    "device health": "DEVICE_HEALTH",
    "computer slow": "DEVICE_HEALTH",
    "laptop slow": "DEVICE_HEALTH",
    "cpu usage": "DEVICE_HEALTH",
    "system health": "DEVICE_HEALTH",
}

# All supported categories
_SUPPORTED_CATEGORIES: frozenset = frozenset({
    "PASSWORD_RESET",
    "VPN",
    "GUEST_WIFI",
    "SHARED_MAILBOX",
    "IT_ASSET_ALLOCATION",
    "OUTLOOK",
    "PRINTER",
    "SAP",
    "SOFTWARE_INSTALLATION",
    "DEVICE_HEALTH",
})

# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class KBArticle:
    """
    Immutable, validated representation of a Knowledge Base article.

    All fields map 1-to-1 with the required JSON schema.  Optional fields
    are given safe empty defaults so the engine never raises on access.
    """

    article_id:          str
    title:               str
    category:            str
    keywords:            List[str]
    problem:             str
    symptoms:            List[str]
    troubleshooting_steps: List[Dict[str, Any]]
    verification:        List[str]
    escalation:          Dict[str, Any]
    screenshots:         List[Dict[str, Any]]
    faq:                 List[Dict[str, Any]]

    # Optional fields present in some articles
    version:             str                    = "1.0"
    source:              str                    = ""
    status:              str                    = "published"
    prerequisites:       List[str]              = field(default_factory=list)
    common_errors:       List[Dict[str, Any]]   = field(default_factory=list)
    related_articles:    List[str]              = field(default_factory=list)

    # Legacy compat: resolution_steps is derived from troubleshooting_steps
    @property
    def resolution_steps(self) -> List[str]:
        """Return step instructions as a plain string list (legacy compat)."""
        return [
            s.get("instruction", s.get("title", ""))
            for s in self.troubleshooting_steps
            if isinstance(s, dict)
        ]

    def to_dict(self) -> dict:
        """Serialise to a plain dict for API responses."""
        return {
            "article_id":           self.article_id,
            "title":                self.title,
            "category":             self.category,
            "keywords":             self.keywords,
            "problem":              self.problem,
            "symptoms":             self.symptoms,
            "troubleshooting_steps": self.troubleshooting_steps,
            "resolution_steps":     self.resolution_steps,
            "verification":         self.verification,
            "escalation":           self.escalation,
            "screenshots":          self.screenshots,
            "faq":                  self.faq,
            "version":              self.version,
            "source":               self.source,
            "status":               self.status,
            "prerequisites":        self.prerequisites,
            "common_errors":        self.common_errors,
            "related_articles":     self.related_articles,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Internal engine state (read-only after load_articles())
# ─────────────────────────────────────────────────────────────────────────────

_load_lock: threading.Lock = threading.Lock()
_articles_cache:  List[KBArticle]         = []
_id_index:        Dict[str, KBArticle]    = {}   # article_id → article
_cat_index:       Dict[str, KBArticle]    = {}   # category   → article
_keyword_index:   Dict[str, List[str]]    = {}   # keyword    → [article_ids]


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def _validate(data: dict, path: str) -> Optional[KBArticle]:
    """
    Validate a parsed JSON dict against REQUIRED_FIELDS.

    Returns a KBArticle on success, None on failure (after logging a warning).
    Never raises.
    """
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        logger.warning(
            "KnowledgeEngine: Skipping %s — missing required fields: %s",
            path, missing,
        )
        return None

    try:
        return KBArticle(
            article_id          = str(data["article_id"]).strip(),
            title               = str(data["title"]).strip(),
            category            = str(data["category"]).upper().strip(),
            keywords            = [str(k) for k in data.get("keywords", [])],
            problem             = str(data["problem"]).strip(),
            symptoms            = [str(s) for s in data.get("symptoms", [])],
            troubleshooting_steps = data.get("troubleshooting_steps", []),
            verification        = [str(v) for v in data.get("verification", [])],
            escalation          = data.get("escalation") or {},
            screenshots         = data.get("screenshots", []),
            faq                 = data.get("faq", []),
            version             = str(data.get("version", "1.0")),
            source              = str(data.get("source", "")),
            status              = str(data.get("status", "published")).strip(),
            prerequisites       = [str(p) for p in data.get("prerequisites", [])],
            common_errors       = data.get("common_errors", []),
            related_articles    = [str(r) for r in data.get("related_articles", [])],
        )
    except Exception:
        logger.exception("KnowledgeEngine: Failed to construct KBArticle from %s", path)
        return None


def _build_index(articles: List[KBArticle]) -> None:
    """Build in-memory lookup indices from the loaded articles list."""
    global _id_index, _cat_index, _keyword_index
    id_idx:  Dict[str, KBArticle]  = {}
    cat_idx: Dict[str, KBArticle]  = {}
    kw_idx:  Dict[str, List[str]]  = {}

    for art in articles:
        id_idx[art.article_id] = art
        cat_idx[art.category]  = art

        # Index every keyword, symptom word, title word, and problem word
        tokens = set()
        for kw in art.keywords:
            tokens.add(_normalize(kw))
        for sym in art.symptoms:
            for tok in _normalize(sym).split():
                tokens.add(tok)
        for tok in _normalize(art.title).split():
            tokens.add(tok)
        for tok in _normalize(art.problem).split():
            tokens.add(tok)

        for tok in tokens:
            if tok:
                kw_idx.setdefault(tok, [])
                if art.article_id not in kw_idx[tok]:
                    kw_idx[tok].append(art.article_id)

    _id_index      = id_idx
    _cat_index     = cat_idx
    _keyword_index = kw_idx
    logger.info(
        "KnowledgeEngine: Index built — %d articles, %d indexed tokens",
        len(articles), len(kw_idx),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API — Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

def load_articles() -> None:
    """
    Auto-discover and load every *.json file from KB_DIR into memory.

    Thread-safe.  Called once at startup.  Articles are validated; any
    article that fails validation is skipped with a warning — the engine
    never crashes on malformed input.
    """
    global _articles_cache

    with _load_lock:
        loaded: List[KBArticle] = []

        if not os.path.isdir(KB_DIR):
            logger.warning(
                "KnowledgeEngine: Knowledge base directory not found: %s — "
                "no articles loaded.",
                KB_DIR,
            )
            _articles_cache = []
            _build_index([])
            return

        for filename in sorted(os.listdir(KB_DIR)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(KB_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "KnowledgeEngine: Malformed JSON in %s — skipping. Error: %s",
                    filepath, exc,
                )
                continue
            except Exception:
                logger.exception(
                    "KnowledgeEngine: Could not read file %s — skipping.", filepath
                )
                continue

            article = _validate(data, filepath)
            if article is not None and article.status == "published":
                loaded.append(article)

        _articles_cache = loaded
        _build_index(loaded)
        logger.info(
            "KnowledgeEngine: Loaded %d articles from %s",
            len(loaded), KB_DIR,
        )


def _ensure_loaded() -> None:
    """Lazy-load articles on first access if not already initialised."""
    if not _articles_cache:
        load_articles()


# ─────────────────────────────────────────────────────────────────────────────
# Public API — Search
# ─────────────────────────────────────────────────────────────────────────────

def search(query: str) -> dict:
    """
    Weighted, fuzzy-aware search across all loaded KB articles.

    Scoring weights
    ---------------
    Category alias match  : +5.0
    Title match           : +4.0
    Keyword match         : +3.0
    Symptom match         : +2.0
    Problem text match    : +2.0

    Returns
    -------
    dict with keys:
        ``article``          – full article dict or None
        ``confidence``       – float [0.0, 1.0]
        ``matched_keywords`` – list[str] of tokens that contributed to score
        ``score``            – raw float score
    """
    _ensure_loaded()

    if not query or not query.strip():
        return {"article": None, "confidence": 0.0, "matched_keywords": [], "score": 0.0}

    norm_query  = _normalize(query)
    query_toks  = set(norm_query.split())

    logger.debug("KnowledgeEngine.search: query=%r tokens=%s", query, query_toks)

    scores: Dict[str, float]       = {}
    matched_kw: Dict[str, List[str]] = {}

    def _add(article_id: str, pts: float, token: str = "") -> None:
        scores[article_id]     = scores.get(article_id, 0.0) + pts
        matched_kw.setdefault(article_id, [])
        if token and token not in matched_kw[article_id]:
            matched_kw[article_id].append(token)

    # 1. Fuzzy alias check — try longest alias first
    sorted_aliases = sorted(_CATEGORY_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        if alias in norm_query:
            cat = _CATEGORY_ALIASES[alias]
            art = _cat_index.get(cat)
            if art:
                _add(art.article_id, SCORE_CATEGORY_MATCH, alias)

    # 2. Token-level inverted-index lookup
    for tok in query_toks:
        if not tok:
            continue
        # Exact token match
        for aid in _keyword_index.get(tok, []):
            _add(aid, SCORE_KEYWORD_MATCH, tok)
        # Partial token match (tok is prefix of an indexed token)
        if len(tok) >= 3:
            for idx_tok, aids in _keyword_index.items():
                if idx_tok.startswith(tok) and idx_tok != tok:
                    for aid in aids:
                        _add(aid, SCORE_KEYWORD_MATCH * 0.5, tok)

    # 3. Per-article field scoring
    for art in _articles_cache:
        aid = art.article_id

        # Category name substring
        norm_cat = _normalize(art.category.replace("_", " "))
        if norm_cat in norm_query or any(t in norm_cat.split() for t in query_toks):
            _add(aid, SCORE_CATEGORY_MATCH)

        # Title
        norm_title = _normalize(art.title)
        if norm_query in norm_title:
            _add(aid, SCORE_TITLE_MATCH * 2, "title")
        else:
            for tok in query_toks:
                if tok in norm_title.split():
                    _add(aid, SCORE_TITLE_MATCH, tok)

        # Keywords
        for kw in art.keywords:
            norm_kw = _normalize(kw)
            if norm_kw == norm_query:
                _add(aid, SCORE_KEYWORD_MATCH * 2, kw)
            elif norm_kw in norm_query or any(t in norm_kw.split() for t in query_toks):
                _add(aid, SCORE_KEYWORD_MATCH, kw)

        # Symptoms
        for sym in art.symptoms:
            norm_sym = _normalize(sym)
            if any(t in norm_sym.split() for t in query_toks):
                _add(aid, SCORE_SYMPTOM_MATCH, sym)

        # Problem description
        norm_prob = _normalize(art.problem)
        for tok in query_toks:
            if tok in norm_prob.split():
                _add(aid, SCORE_PROBLEM_MATCH, tok)

    if not scores:
        return {"article": None, "confidence": 0.0, "matched_keywords": [], "score": 0.0}

    best_id    = max(scores, key=lambda k: scores[k])
    best_score = scores[best_id]
    confidence = round(min(1.0, best_score / _SCORE_CEILING), 3)

    if confidence < MIN_CONFIDENCE:
        return {"article": None, "confidence": 0.0, "matched_keywords": [], "score": 0.0}

    best_art = _id_index.get(best_id)
    logger.info(
        "KnowledgeEngine.search: query=%r → %s (confidence=%.3f, score=%.1f)",
        query, best_id, confidence, best_score,
    )

    return {
        "article":          best_art.to_dict() if best_art else None,
        "confidence":       confidence,
        "matched_keywords": matched_kw.get(best_id, []),
        "score":            round(best_score, 2),
    }


def search_by_category(category: str) -> Optional[dict]:
    """
    Return the article for an exact category string match.

    Backward compatible — returns None if no article is loaded for that
    category (no placeholder generation).
    """
    _ensure_loaded()
    art = _cat_index.get(category.upper().strip())
    return art.to_dict() if art else None


# ─────────────────────────────────────────────────────────────────────────────
# Public API — Article Retrieval
# ─────────────────────────────────────────────────────────────────────────────

def get_article(article_id: str) -> Optional[dict]:
    """Return the complete article dict for the given article_id, or None."""
    _ensure_loaded()
    art = _id_index.get(article_id.strip())
    return art.to_dict() if art else None


def get_steps(article_id: str) -> List[dict]:
    """
    Return all troubleshooting steps for the given article.

    Each step is a dict with at minimum: step, title, instruction.
    """
    art = get_article(article_id)
    return art.get("troubleshooting_steps", []) if art else []


def get_step(article_id: str, step_number: int) -> Optional[dict]:
    """
    Return a single troubleshooting step by its 1-based step number.

    Returns None if the article or step is not found.
    """
    for step in get_steps(article_id):
        if isinstance(step, dict) and step.get("step") == step_number:
            return step
    return None


def next_step(article_id: str, current_step: int) -> Optional[dict]:
    """
    Return the step immediately after *current_step*.

    Returns None if *current_step* is already the last step or the article
    does not exist.
    """
    return get_step(article_id, current_step + 1)


def previous_step(article_id: str, current_step: int) -> Optional[dict]:
    """
    Return the step immediately before *current_step*.

    Returns None if *current_step* is 1 (first step) or the article does
    not exist.
    """
    if current_step <= 1:
        return None
    return get_step(article_id, current_step - 1)


def get_verification(article_id: str) -> List[str]:
    """Return the verification checklist for the given article."""
    art = get_article(article_id)
    return art.get("verification", []) if art else []


def get_escalation(article_id: str) -> Optional[dict]:
    """Return the escalation policy dict for the given article, or None."""
    art = get_article(article_id)
    return art.get("escalation") if art else None


def get_screenshots(article_id: str) -> List[dict]:
    """Return the screenshots metadata list for the given article."""
    art = get_article(article_id)
    return art.get("screenshots", []) if art else []


def list_categories() -> List[str]:
    """Return a sorted list of all categories present in loaded articles."""
    _ensure_loaded()
    return sorted(_cat_index.keys())


def list_articles() -> List[dict]:
    """
    Return a summary list of all loaded articles.

    Each entry contains: article_id, title, category.
    """
    _ensure_loaded()
    return [
        {"article_id": a.article_id, "title": a.title, "category": a.category}
        for a in _articles_cache
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Legacy API — Backward Compatibility
# ─────────────────────────────────────────────────────────────────────────────

def get_troubleshooting_steps(article_id: str) -> list:
    """
    Legacy helper — returns troubleshooting steps.

    Supports both old (resolution_steps as str list) and new
    (troubleshooting_steps as dict list) formats.
    """
    art = get_article(article_id)
    if not art:
        return []
    # Prefer structured steps if present
    structured = art.get("troubleshooting_steps", [])
    if structured:
        return structured
    return art.get("resolution_steps", [])


def get_guide_content(category: str) -> Tuple[str, str]:
    """
    Legacy loader: converts structured article into a text block.

    Returns ``(content_string, filename)`` exactly as older callers expect.
    """
    _ensure_loaded()
    art = search_by_category(category)
    if not art:
        return (
            f"No specific guide found for category: {category}. "
            "Please contact IT support.",
            "N/A",
        )

    steps = art.get("troubleshooting_steps", [])
    if not steps:
        # Fall back to legacy resolution_steps if present
        steps_text = "\n".join(
            f"{i}. {s}" for i, s in enumerate(art.get("resolution_steps", []), 1)
        )
    else:
        steps_text = "\n".join(
            f"{s.get('step', i)}. {s.get('instruction', s.get('title', ''))}"
            for i, s in enumerate(steps, 1)
            if isinstance(s, dict)
        )

    content = (
        f"Article: {art.get('title')}\n"
        f"Problem: {art.get('problem')}\n\n"
        f"Troubleshooting Steps:\n{steps_text}"
    )
    filename = f"{category.lower()}_guide.json"
    return content.strip(), filename


def get_vpn_guide() -> Tuple[str, str]:
    """Legacy convenience wrapper for VPN guide."""
    return get_guide_content("VPN")


def get_outlook_guide() -> Tuple[str, str]:
    """Legacy convenience wrapper for Outlook guide."""
    return get_guide_content("OUTLOOK")


def get_software_installation_guide() -> Tuple[str, str]:
    """Legacy convenience wrapper for Software Installation guide."""
    return get_guide_content("SOFTWARE_INSTALLATION")


def get_password_reset_guide() -> Tuple[str, str]:
    """Legacy convenience wrapper for Password Reset guide."""
    return get_guide_content("PASSWORD_RESET")


def get_printer_guide() -> Tuple[str, str]:
    """Legacy convenience wrapper for Printer guide."""
    return get_guide_content("PRINTER")
