import os
import logging

logger = logging.getLogger("it-agent-backend")

# Base directory for the knowledge base (c:\Projects\it-agent\knowledge_base)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "knowledge_base"))

# Mapping of categories to their directory and filename
RAG_MAPPING = {
    "VPN": ("vpn", "vpn_guide.txt"),
    "OUTLOOK": ("outlook", "outlook_guide.txt"),
    "PRINTER": ("printer", "printer_guide.txt"),
    "SOFTWARE_INSTALLATION": ("software_installation", "software_installation_guide.txt"),
    "PASSWORD_RESET": ("password_reset", "password_reset_guide.txt")
}

def get_document_for_category(category: str) -> str:
    """
    Returns the document filename mapped to the given category.
    Returns 'N/A' if category is invalid or has no mapped document.
    """
    category_upper = category.strip().upper()
    if category_upper in RAG_MAPPING:
        return RAG_MAPPING[category_upper][1]
    return "N/A"

def load_knowledge_context(category: str) -> str:
    """
    Loads and returns the text content of the document mapped to the category.
    Handles missing files, empty files, or invalid categories with fallback responses.
    """
    category_upper = category.strip().upper()
    if category_upper not in RAG_MAPPING:
        logger.warning("RAG Service: Category '%s' is not mapped to any document.", category)
        return ""
        
    subfolder, filename = RAG_MAPPING[category_upper]
    file_path = os.path.join(BASE_DIR, subfolder, filename)
    
    if not os.path.exists(file_path):
        logger.error("RAG Service: File not found at path: %s", file_path)
        return ""
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            logger.warning("RAG Service: File is empty: %s", file_path)
            return ""
        logger.info("RAG Service: Successfully loaded knowledge from %s", filename)
        return content
    except Exception as e:
        logger.error("RAG Service: Exception reading knowledge file %s: %s", filename, e)
        return ""

def retrieve_context(category: str) -> str:
    """
    Wrapper for backward compatibility. Loads context for the category.
    """
    return load_knowledge_context(category)

def get_relevant_document(category: str) -> str:
    """
    Wrapper for backward compatibility. Returns the document path.
    """
    category_upper = category.strip().upper()
    if category_upper in RAG_MAPPING:
        subfolder, filename = RAG_MAPPING[category_upper]
        return f"knowledge_base/{subfolder}/{filename}"
    return "N/A"

# =====================================================================
# FUTURE UPGRADE PATH TO VECTOR DATABASE RAG (TODO checklist):
# =====================================================================
# To upgrade this RAG service to use a semantic vector database:
# 
# 1. Embeddings:
#    Use Sentence Transformers (e.g., HuggingFace 'all-MiniLM-L6-v2') 
#    to generate dense vector representations of queries and documents.
# 
# 2. Vector DB Integration:
#    - FAISS / pgvector: For simpler deployment, store chunk embeddings 
#      and execute flat/index-based L2 or Cosine distance searches.
#    - Qdrant: Connect using `qdrant-client` to perform remote vector 
#      similarity lookups with pre-filters on the metadata (e.g. category).
# 
# 3. Document Chunking:
#    Instead of loading the entire file, chunk documents (e.g., using 
#    RecursiveCharacterTextSplitter) and query the top-k chunks.
# =====================================================================
