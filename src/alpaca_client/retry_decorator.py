import time
import random
import logging
from functools import wraps
from alpaca.common.exceptions import APIError

logger = logging.getLogger("AlpacaRetry")

def alpaca_retryable(max_retries: int = 5, base_delay: float = 1.0):
    """Decorator to retry Alpaca API calls with exponential backoff and rate-limit awareness."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    status_code = None
                    if isinstance(e, APIError):
                        status_code = getattr(e, "status_code", None) or getattr(e, "code", None)
                    
                    if status_code is None:
                        err_str = str(e)
                        if "429" in err_str:
                            status_code = 429
                        elif "408" in err_str or "timeout" in err_str.lower():
                            status_code = 408

                    # Fail fast on non-retryable errors
                    if status_code is not None:
                        if status_code in [400, 401, 403, 404, 422]:
                            logger.error(f"Alpaca non-retryable error (status: {status_code}) on {func.__name__}: {e}")
                            raise e

                    if attempt == max_retries:
                        logger.error(f"Alpaca API failed after {max_retries} attempts on {func.__name__}: {e}")
                        raise e

                    if status_code == 429:
                        sleep_time = 30.0
                        logger.warning(f"Alpaca rate limit (429) hit on {func.__name__}. Retrying in 30.0s (attempt {attempt}/{max_retries}). Error: {e}")
                    else:
                        jitter = random.uniform(0.8, 1.2)
                        sleep_time = min(delay * jitter, 60.0)
                        logger.warning(f"Alpaca API error (status: {status_code}) on {func.__name__}. Retrying in {sleep_time:.2f}s (attempt {attempt}/{max_retries}). Error: {e}")
                        delay = min(delay * 2, 60.0)

                    time.sleep(sleep_time)
            return None
        return wrapper
    return decorator
