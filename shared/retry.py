"""
Retry utilities with exponential backoff for resilient service calls.
"""

import time
import random
from typing import Callable, TypeVar, Optional, List
from functools import wraps

from shared.logging_config import setup_logging

logger = setup_logging("retry")

T = TypeVar('T')


def exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to prevent thundering herd
        exceptions: Tuple of exceptions to catch and retry
    
    Usage:
        @exponential_backoff(max_retries=3, initial_delay=1.0)
        def unreliable_function():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries",
                            extra={
                                'function': func.__name__,
                                'attempt': attempt + 1,
                                'max_retries': max_retries,
                                'exception': str(e)
                            }
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    if jitter:
                        # Add random jitter (±25%)
                        jitter_amount = delay * 0.25 * (2 * random.random() - 1)
                        actual_delay = delay + jitter_amount
                    else:
                        actual_delay = delay
                    
                    actual_delay = min(actual_delay, max_delay)
                    
                    logger.warning(
                        f"Function {func.__name__} failed, retrying in {actual_delay:.2f}s",
                        extra={
                            'function': func.__name__,
                            'attempt': attempt + 1,
                            'max_retries': max_retries,
                            'delay': actual_delay,
                            'exception': str(e)
                        }
                    )
                    
                    time.sleep(actual_delay)
                    delay *= exponential_base
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def retry_with_idempotency(
    idempotency_key: str,
    idempotency_store: Callable[[str, Callable], T],
    max_retries: int = 3
):
    """
    Retry decorator with idempotency key support.
    
    Args:
        idempotency_key: Key to use for idempotency check
        idempotency_store: Function to check/store idempotency results
        max_retries: Maximum retries
    
    Usage:
        @retry_with_idempotency(
            idempotency_key=lambda *args, **kwargs: kwargs.get('event_id'),
            idempotency_store=redis_idempotency_store
        )
        def process_event(event_id: str):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Get idempotency key
            if callable(idempotency_key):
                key = idempotency_key(*args, **kwargs)
            else:
                key = idempotency_key
            
            # Check if already processed
            cached_result = idempotency_store.get(key)
            if cached_result is not None:
                logger.info(
                    f"Idempotent call detected for {func.__name__}",
                    extra={'idempotency_key': key, 'function': func.__name__}
                )
                return cached_result
            
            # Execute with retry
            @exponential_backoff(max_retries=max_retries)
            def execute():
                result = func(*args, **kwargs)
                idempotency_store.set(key, result)
                return result
            
            return execute()
        
        return wrapper
    return decorator

