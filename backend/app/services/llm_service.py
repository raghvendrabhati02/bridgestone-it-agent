import os
import logging
from dotenv import load_dotenv
from app.services.ai_provider import get_ai_provider

logger = logging.getLogger("it-agent-backend")

# Load environment variables from .env
load_dotenv()
if not os.getenv("GEMINI_API_KEY"):
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    load_dotenv(dotenv_path=env_path)

def generate_response(user_message: str, knowledge_context: str | None = None) -> str | dict:
    """
    Generates a response from the active AI provider based on the user's message/prompt.
    If knowledge_context is provided, grounds the model using the RAG prompt structure.
    Gracefully handles API exceptions, missing configurations, and empty responses.
    """
    provider = get_ai_provider()
    return provider.generate_response(user_message, knowledge_context)

