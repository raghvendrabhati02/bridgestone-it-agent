"""
handlers/kb_handler.py
─────────────────────────────────────────────────────────────────────────────
Handles tool:
    SEARCH_KNOWLEDGE_BASE  → rag_service.load_knowledge_context()
"""

from app.services.handlers import ok

TOOL = "SEARCH_KNOWLEDGE_BASE"


def handle(params: dict) -> dict:
    """→ rag_service.load_knowledge_context()"""
    from app.services.rag_service import load_knowledge_context
    category = params.get("category", "GENERAL")
    context  = load_knowledge_context(category)
    return ok(TOOL, data={"context": context, "category": category}, message=f"Knowledge context retrieved for category '{category}'.")
