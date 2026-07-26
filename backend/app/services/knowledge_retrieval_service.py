"""
knowledge_retrieval_service.py
──────────────────────────────────────────────────────────────────────────────
Enterprise Knowledge Retrieval Service for the Bridgestone IT Agent.

Responsibilities
----------------
• Retrieve relevant enterprise KB documents for a given query and category.
• Rank results by confidence score.
• Expose a stable interface designed for future evolution (hybrid search,
  reranking, deduplication, embedding-based retrieval).

Design contracts (MUST NOT be violated)
----------------------------------------
  ✓  Retrieves ONLY — never reasons, never summarizes, never generates text.
  ✓  Delegates to the existing knowledge_service module (single KB source).
  ✓  content_summary field contains problem + symptoms digest, NOT raw articles.
  ✓  Confidence is normalised [0.0, 1.0] from knowledge_service scoring.
  ✓  Never raises on empty or partial results — always returns a list (possibly []).

Future evolution hooks (interface defined, not implemented in Phase 1)
-----------------------------------------------------------------------
  • rerank(docs, query)         — cross-encoder / LLM-based reranking
  • deduplicate(docs)           — remove overlapping articles
  • hybrid_search(query, emb)   — dense + sparse retrieval fusion
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import app.services.knowledge_service as knowledge_service

logger = logging.getLogger("it-agent-backend")


# ── Data Contract ─────────────────────────────────────────────────────────────

@dataclass
class RetrievedDocument:
    """
    A single KB article retrieved and prepared for use by the reasoning layer.

    content_summary is a human-readable digest of problem + symptoms — it is
    intentionally *not* the full article.  The orchestrator must never dump raw
    article text directly to users.
    """
    article_id: str
    title: str
    category: str
    content_summary: str                  # problem + key symptoms (digest only)
    troubleshooting_steps: List[Dict[str, Any]]
    escalation_info: Dict[str, Any]
    confidence: float                     # normalised [0.0, 1.0]
    matched_keywords: List[str]
    rank: int                             # 1 = highest


# ── Service ───────────────────────────────────────────────────────────────────

class KnowledgeRetrievalService:
    """
    Enterprise Knowledge Retrieval Service.

    Wraps the existing knowledge_service module to provide a stable,
    evolvable retrieval interface for the TroubleshootingOrchestrator.
    """

    DEFAULT_MAX_RESULTS: int = 3
    DEFAULT_MIN_CONFIDENCE: float = 0.10

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = DEFAULT_MAX_RESULTS,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> List[RetrievedDocument]:
        """
        Retrieve and rank relevant KB articles for a given query.

        Args:
            query:          Free-text user issue description or synthesised query.
            category:       Optional ITSM category to prioritise (e.g. "VPN").
            max_results:    Maximum number of documents to return.
            min_confidence: Minimum confidence threshold; articles below this
                            are discarded.

        Returns:
            List of RetrievedDocument, sorted by confidence descending.
            Returns [] if no articles meet the threshold — never raises.
        """
        t_start = time.monotonic()
        results: List[RetrievedDocument] = []

        logger.info(
            ">>> ENTRY [KnowledgeRetrievalService.retrieve]: query=%r, category=%r, "
            "max_results=%d, min_confidence=%.2f",
            query[:80], category or "<none>", max_results, min_confidence,
        )

        if not query or not query.strip():
            logger.warning("[KnowledgeRetrievalService]: Empty query — returning [].")
            return []

        # Build search queries: synthesise category-augmented query when a hint is given
        search_queries = [query]
        if category:
            search_queries.insert(0, f"{category} {query}")

        # Collect candidate article IDs with best scores across all queries
        best_scores: Dict[str, float] = {}
        best_matched_kw: Dict[str, List[str]] = {}
        best_articles: Dict[str, Dict] = {}

        for sq in search_queries:
            try:
                result = knowledge_service.search(sq)
                article = result.get("article")
                if article is None:
                    continue
                aid = article.get("article_id", "")
                if not aid:
                    continue
                conf = float(result.get("confidence", 0.0))
                kws = result.get("matched_keywords", [])

                # Keep the best confidence seen for this article
                if aid not in best_scores or conf > best_scores[aid]:
                    best_scores[aid] = conf
                    best_matched_kw[aid] = kws
                    best_articles[aid] = article
            except Exception as exc:
                logger.warning(
                    "[KnowledgeRetrievalService]: knowledge_service.search failed for %r: %s",
                    sq, exc,
                )

        # Filter by confidence threshold and sort by score descending
        qualified = [
            (aid, score)
            for aid, score in best_scores.items()
            if score >= min_confidence
        ]
        qualified.sort(key=lambda x: x[1], reverse=True)
        qualified = qualified[:max_results]

        # Construct RetrievedDocument for each qualified article
        for rank, (aid, conf) in enumerate(qualified, start=1):
            article = best_articles[aid]
            doc = self._build_document(
                article=article,
                confidence=conf,
                matched_keywords=best_matched_kw.get(aid, []),
                rank=rank,
            )
            results.append(doc)

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "<<< EXIT [KnowledgeRetrievalService.retrieve]: returned %d documents in %dms",
            len(results), elapsed_ms,
        )
        return results

    # ── Future Evolution Interface Stubs ──────────────────────────────────────

    def rerank(
        self,
        docs: List[RetrievedDocument],
        query: str,
    ) -> List[RetrievedDocument]:
        """
        [Phase 2+] Cross-encoder or LLM-based reranking of retrieved documents.
        Currently a no-op pass-through (returns docs unchanged).
        """
        logger.debug("[KnowledgeRetrievalService.rerank]: Not implemented in Phase 1 — pass-through.")
        return docs

    def deduplicate(self, docs: List[RetrievedDocument]) -> List[RetrievedDocument]:
        """
        [Phase 2+] Remove semantically overlapping or identical articles.
        Currently deduplicates by article_id only.
        """
        seen: set[str] = set()
        unique: List[RetrievedDocument] = []
        for doc in docs:
            if doc.article_id not in seen:
                seen.add(doc.article_id)
                unique.append(doc)
        return unique

    def hybrid_search(
        self,
        query: str,
        embedding: Optional[List[float]] = None,
        category: Optional[str] = None,
        max_results: int = DEFAULT_MAX_RESULTS,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> List[RetrievedDocument]:
        """
        [Phase 2+] Hybrid dense + sparse retrieval fusion.
        Currently falls back to standard keyword retrieve().
        """
        logger.debug(
            "[KnowledgeRetrievalService.hybrid_search]: Embedding-based search "
            "not implemented in Phase 1 — falling back to keyword retrieve()."
        )
        return self.retrieve(query, category=category, max_results=max_results,
                             min_confidence=min_confidence)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _build_document(
        self,
        article: Dict[str, Any],
        confidence: float,
        matched_keywords: List[str],
        rank: int,
    ) -> RetrievedDocument:
        """Construct a RetrievedDocument from a raw knowledge_service article dict."""
        problem = article.get("problem", "")
        symptoms: List[str] = article.get("symptoms", [])

        # Build a concise digest — never include full step text here
        symptom_summary = "; ".join(symptoms[:3]) if symptoms else ""
        content_summary = problem
        if symptom_summary:
            content_summary = f"{problem} Common symptoms: {symptom_summary}"

        return RetrievedDocument(
            article_id=article.get("article_id", ""),
            title=article.get("title", ""),
            category=article.get("category", ""),
            content_summary=content_summary.strip(),
            troubleshooting_steps=article.get("troubleshooting_steps", []),
            escalation_info=article.get("escalation", {}),
            confidence=round(min(max(confidence, 0.0), 1.0), 4),
            matched_keywords=matched_keywords,
            rank=rank,
        )
