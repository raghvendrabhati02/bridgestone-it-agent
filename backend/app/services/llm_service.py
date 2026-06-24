import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger("it-agent-backend")

# Load environment variables from .env
load_dotenv()
if not os.getenv("GEMINI_API_KEY"):
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    logger.error("LLM Service: GEMINI_API_KEY is not defined in environment variables.")
else:
    # Configure the Google Generative AI SDK
    genai.configure(api_key=api_key)

def generate_response(user_message: str, knowledge_context: str | None = None) -> str | dict:
    """
    Generates a response from the Gemini model based on the user's message/prompt.
    If knowledge_context is provided, grounds the model using the RAG prompt structure.
    Gracefully handles API exceptions, missing configurations, and empty responses.
    """
    from app.core.metrics import (
        LLM_REQUESTS_TOTAL,
        LLM_SUCCESS_TOTAL,
        LLM_FAILURES_TOTAL,
        LLM_LATENCY_SECONDS,
        LLM_TOKEN_USAGE_TOTAL,
        LLM_RATE_LIMIT_ERRORS_TOTAL,
        LLM_FALLBACK_EVENTS_TOTAL
    )
    import time

    try:
        LLM_REQUESTS_TOTAL.inc()
    except Exception:
        pass

    logger.info("LLM Service: Incoming user message: %s", user_message)
    logger.info("LLM Service: Retrieved knowledge context: %s", knowledge_context)

    if not api_key:
        logger.error("LLM Service: Generation cancelled due to missing API key configuration.")
        try:
            LLM_FAILURES_TOTAL.labels(error_type="missing_api_key").inc()
            LLM_FALLBACK_EVENTS_TOTAL.inc()
        except Exception:
            pass
        return {
            "debug_error": "System Error: Gemini API key is missing. Please check backend configuration."
        }
        
    # Build prompt structure based on presence of RAG context
    if knowledge_context:
        prompt = (
            "You are Bridgestone's IT Support Agent.\n"
            "Use ONLY the knowledge provided below when answering.\n\n"
            "Knowledge Base:\n"
            f"{knowledge_context}\n\n"
            "User Question:\n"
            f"{user_message}\n\n"
            "Provide a concise troubleshooting response."
        )
    else:
        prompt = user_message
        
    logger.info("LLM Service: Prompt sent to Gemini:\n%s", prompt)
    
    start_time = time.time()
    try:
        # Use gemini-2.5-flash-lite as the default fast helper model
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        
        # Execute generation call with a 15-second timeout
        response = model.generate_content(
            prompt,
            request_options={"timeout": 15.0}
        )
        
        duration = time.time() - start_time
        try:
            LLM_LATENCY_SECONDS.observe(duration)
        except Exception:
            pass

        # Log raw response object
        logger.info("LLM Service: Raw Gemini response: %s", response)
        
        if not response or not response.text:
            logger.warning("LLM Service: Received empty text response from Gemini.")
            try:
                LLM_FAILURES_TOTAL.labels(error_type="empty_response").inc()
                LLM_FALLBACK_EVENTS_TOTAL.inc()
            except Exception:
                pass
            return {
                "debug_error": "Empty response received from Gemini."
            }
            
        parsed_text = response.text.strip()
        logger.info("LLM Service: Parsed response: %s", parsed_text)

        try:
            LLM_SUCCESS_TOTAL.inc()
            usage = getattr(response, "usage_metadata", None)
            if usage:
                prompt_tokens = getattr(usage, "prompt_token_count", 0)
                candidate_tokens = getattr(usage, "candidates_token_count", 0)
                if prompt_tokens:
                    LLM_TOKEN_USAGE_TOTAL.labels(token_type="prompt_tokens").inc(prompt_tokens)
                if candidate_tokens:
                    LLM_TOKEN_USAGE_TOTAL.labels(token_type="candidate_tokens").inc(candidate_tokens)
        except Exception as mex:
            logger.warning("Failed to record LLM usage metrics: %s", mex)

        return parsed_text
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error("LLM Service: Exception occurred during Gemini generate call: %s", e, exc_info=True)
        
        error_str = str(e)
        error_type = type(e).__name__
        
        # Check for rate limiting status (429 or resource exhausted)
        is_rate_limit = "429" in error_str or "resource exhausted" in error_str.lower()
        
        try:
            LLM_LATENCY_SECONDS.observe(duration)
            if is_rate_limit:
                LLM_RATE_LIMIT_ERRORS_TOTAL.inc()
                LLM_FAILURES_TOTAL.labels(error_type="rate_limit").inc()
            else:
                LLM_FAILURES_TOTAL.labels(error_type=error_type).inc()
            LLM_FALLBACK_EVENTS_TOTAL.inc()
        except Exception:
            pass

        return {
            "debug_error": error_str
        }

