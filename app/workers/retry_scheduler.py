from app.core.config import settings

def calculate_backoff_delay(retry_count: int) -> float:
    """
    Calculate exponential backoff delay for retries.
    Formula: base_delay_seconds * (multiplier ** retry_count)
    """
    base_delay = settings.RETRY_BASE_DELAY_SECONDS
    multiplier = settings.RETRY_MULTIPLIER
    
    # retry_count is 0-indexed for the first retry. 
    # If the first attempt fails, retry_count is 0 when this is called, 
    # so delay = 30 * (4 ** 0) = 30s.
    # Second retry (retry_count=1) -> 30 * (4 ** 1) = 120s (2m).
    # Third retry (retry_count=2) -> 30 * (4 ** 2) = 480s (8m).
    
    return float(base_delay * (multiplier ** retry_count))

def should_retry(current_retry_count: int, max_retries: int) -> bool:
    """
    Determine if a notification should be retried based on current attempt count.
    """
    return current_retry_count < max_retries
