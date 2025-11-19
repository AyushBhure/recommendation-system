"""
Circuit breaker pattern implementation for resilient external service calls.
Prevents cascading failures by stopping requests to failing services.
"""

import time
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps

from shared.logging_config import setup_logging

logger = setup_logging("circuit_breaker")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker implementation.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing recovery, allow limited requests
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        name: str = "circuit_breaker"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            half_open_max_calls: Max calls allowed in half-open state
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Function result
        
        Raises:
            Exception: If circuit is open or function fails
        """
        # Check if circuit should transition
        self._check_state_transition()
        
        # Reject if circuit is open
        if self.state == CircuitState.OPEN:
            logger.warning(
                f"Circuit breaker {self.name} is OPEN, rejecting request",
                extra={'circuit_breaker': self.name, 'state': self.state.value}
            )
            raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _check_state_transition(self):
        """Check and update circuit breaker state."""
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time and \
               time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(
                    f"Circuit breaker {self.name} transitioning to HALF_OPEN",
                    extra={'circuit_breaker': self.name}
                )
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
    
    def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                logger.info(
                    f"Circuit breaker {self.name} transitioning to CLOSED",
                    extra={'circuit_breaker': self.name}
                )
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.half_open_calls = 0
        else:
            # Reset failure count on success
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open goes back to open
            logger.warning(
                f"Circuit breaker {self.name} transitioning back to OPEN",
                extra={'circuit_breaker': self.name}
            )
            self.state = CircuitState.OPEN
            self.half_open_calls = 0
        elif self.failure_count >= self.failure_threshold:
            logger.error(
                f"Circuit breaker {self.name} opening after {self.failure_count} failures",
                extra={'circuit_breaker': self.name, 'failure_count': self.failure_count}
            )
            self.state = CircuitState.OPEN


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    name: Optional[str] = None
):
    """
    Decorator for circuit breaker pattern.
    
    Usage:
        @circuit_breaker(failure_threshold=5, name="external_api")
        def call_external_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            name=name or func.__name__
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        
        return wrapper
    return decorator

