import time
import random
import logging
from functools import wraps

logger = logging.getLogger("it-agent-backend")

def with_retry(retries=3, backoff_factor=2.0, jitter=True):
    """
    Decorator for retrying functions with exponential backoff.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_ex = None
            delay = 1.0  # initial delay in seconds
            for attempt in range(1, retries + 1):
                try:
                    result = func(*args, **kwargs)
                    # Check if the result is a dict indicating a debug_error
                    if isinstance(result, dict) and "debug_error" in result:
                        # Avoid double-retrying at the decorator level when the provider already handles retries
                        return result
                    return result
                except Exception as ex:
                    last_ex = ex
                    logger.warning(
                        "Retry Helper: Attempt %d/%d for '%s' failed with error: %s. Retrying in %.2fs...",
                        attempt, retries, func.__name__, ex, delay
                    )
                    if attempt == retries:
                        break
                    
                    # Sleep with optional jitter
                    sleep_time = delay
                    if jitter:
                        sleep_time += random.uniform(0, 0.5 * delay)
                    time.sleep(sleep_time)
                    delay *= backoff_factor
            
            logger.error("Retry Helper: All %d attempts for '%s' failed.", retries, func.__name__)
            if last_ex:
                raise last_ex
        return wrapper
    return decorator
