"""
Error Recovery Manager

Intelligent error recovery strategies with circuit breakers, retry policies, and graceful degradation.

Features:
- Circuit breaker pattern for external services (Ollama, FastF1, Modal)
- Exponential backoff with jitter for retries
- Graceful degradation with cached data
- Service-specific recovery strategies
- Automatic cleanup on memory errors
- Integration with ErrorTracker for monitoring
"""

import time
import random
import logging
import traceback
import psutil
import os
import gc
from enum import Enum
from typing import Dict, Optional, Callable, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Service is failing, reject requests
    HALF_OPEN = "half_open"    # Testing if service recovered


class ErrorType(Enum):
    """Categorized error types for different recovery strategies"""
    NETWORK_ERROR = "network"
    API_ERROR = "api"
    TIMEOUT_ERROR = "timeout"
    MEMORY_ERROR = "memory"
    DATA_ERROR = "data"
    UNKNOWN_ERROR = "unknown"


@dataclass
class RetryPolicy:
    """Retry policy configuration"""
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0     # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    timeout: Optional[float] = None  # per-attempt timeout


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5        # Open circuit after N failures
    success_threshold: int = 2        # Close circuit after N successes in half-open
    timeout: float = 60.0             # Seconds before attempting recovery
    half_open_max_calls: int = 3      # Max calls in half-open state


@dataclass
class CircuitBreakerState:
    """Runtime state of a circuit breaker"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    opened_at: Optional[float] = None
    half_open_calls: int = 0


class ServiceCircuitBreaker:
    """
    Circuit breaker for external services.

    Prevents cascading failures by temporarily blocking requests to failing services.
    """

    def __init__(self, service_name: str, config: CircuitBreakerConfig):
        self.service_name = service_name
        self.config = config
        self.state = CircuitBreakerState()
        self.lock = Lock()

        logger.info(f"Circuit breaker initialized for {service_name}")

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result from function

        Raises:
            CircuitBreakerOpenError: When circuit is open
            Exception: Original exception from function
        """
        with self.lock:
            current_state = self.state.state

            # Check if circuit is open
            if current_state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if time.time() - self.state.opened_at >= self.config.timeout:
                    # Transition to half-open
                    self.state.state = CircuitState.HALF_OPEN
                    self.state.half_open_calls = 0
                    logger.info(f"Circuit breaker {self.service_name}: OPEN → HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker open for {self.service_name}. "
                        f"Retry in {self.config.timeout - (time.time() - self.state.opened_at):.1f}s"
                    )

            # Check half-open call limit
            if current_state == CircuitState.HALF_OPEN:
                if self.state.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker {self.service_name} in half-open state. "
                        "Max test calls reached."
                    )
                self.state.half_open_calls += 1

        # Execute function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        """Handle successful call"""
        with self.lock:
            if self.state.state == CircuitState.HALF_OPEN:
                self.state.success_count += 1
                logger.info(
                    f"Circuit breaker {self.service_name}: Success in half-open "
                    f"({self.state.success_count}/{self.config.success_threshold})"
                )

                if self.state.success_count >= self.config.success_threshold:
                    # Close circuit
                    self.state.state = CircuitState.CLOSED
                    self.state.failure_count = 0
                    self.state.success_count = 0
                    logger.info(f"Circuit breaker {self.service_name}: HALF_OPEN → CLOSED")
            else:
                # Reset failure count on success
                self.state.failure_count = 0

    def _on_failure(self, error: Exception):
        """Handle failed call"""
        with self.lock:
            self.state.failure_count += 1
            self.state.last_failure_time = time.time()

            if self.state.state == CircuitState.HALF_OPEN:
                # Failed in half-open, go back to open
                self.state.state = CircuitState.OPEN
                self.state.opened_at = time.time()
                self.state.success_count = 0
                logger.warning(
                    f"Circuit breaker {self.service_name}: HALF_OPEN → OPEN "
                    f"(failure: {type(error).__name__})"
                )

            elif self.state.failure_count >= self.config.failure_threshold:
                # Too many failures, open circuit
                self.state.state = CircuitState.OPEN
                self.state.opened_at = time.time()
                logger.warning(
                    f"Circuit breaker {self.service_name}: CLOSED → OPEN "
                    f"(failures: {self.state.failure_count})"
                )

    def get_state(self) -> Dict:
        """Get current circuit breaker state"""
        with self.lock:
            return {
                'service': self.service_name,
                'state': self.state.state.value,
                'failure_count': self.state.failure_count,
                'success_count': self.state.success_count,
                'last_failure': datetime.fromtimestamp(self.state.last_failure_time).isoformat()
                    if self.state.last_failure_time else None,
                'opened_at': datetime.fromtimestamp(self.state.opened_at).isoformat()
                    if self.state.opened_at else None,
            }

    def reset(self):
        """Manually reset circuit breaker (for testing/admin)"""
        with self.lock:
            self.state = CircuitBreakerState()
            logger.info(f"Circuit breaker {self.service_name}: Manually reset")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class RecoveryManager:
    """
    Central error recovery manager with intelligent strategies.

    Features:
    - Circuit breakers for external services
    - Retry policies with exponential backoff
    - Graceful degradation
    - Memory management
    - Integration with ErrorTracker
    """

    def __init__(self, error_tracker=None):
        self.error_tracker = error_tracker
        self.circuit_breakers: Dict[str, ServiceCircuitBreaker] = {}
        self.retry_policies: Dict[ErrorType, RetryPolicy] = {}
        self.lock = Lock()

        # Statistics
        self.recovery_stats = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'circuit_breaker_blocks': 0,
            'graceful_degradations': 0,
            'memory_cleanups': 0,
        }

        # Initialize default components
        self._init_circuit_breakers()
        self._init_retry_policies()

        logger.info("RecoveryManager initialized")

    def _init_circuit_breakers(self):
        """Initialize circuit breakers for external services"""

        # Ollama API (AI inference)
        self.circuit_breakers['ollama'] = ServiceCircuitBreaker(
            'ollama',
            CircuitBreakerConfig(
                failure_threshold=3,        # Fail fast for AI
                success_threshold=2,
                timeout=30.0,               # Retry after 30s
                half_open_max_calls=2,
            )
        )

        # FastF1 API (F1 data downloads)
        self.circuit_breakers['fastf1'] = ServiceCircuitBreaker(
            'fastf1',
            CircuitBreakerConfig(
                failure_threshold=5,        # More lenient (network issues)
                success_threshold=2,
                timeout=60.0,               # Retry after 1 min
                half_open_max_calls=3,
            )
        )

        # Modal GPU function
        self.circuit_breakers['modal'] = ServiceCircuitBreaker(
            'modal',
            CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout=45.0,
                half_open_max_calls=2,
            )
        )

    def _init_retry_policies(self):
        """Initialize retry policies for different error types"""

        # Network errors - aggressive retry
        self.retry_policies[ErrorType.NETWORK_ERROR] = RetryPolicy(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True,
        )

        # API errors - moderate retry
        self.retry_policies[ErrorType.API_ERROR] = RetryPolicy(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True,
        )

        # Timeout errors - fewer retries
        self.retry_policies[ErrorType.TIMEOUT_ERROR] = RetryPolicy(
            max_attempts=2,
            initial_delay=2.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True,
        )

        # Memory errors - no retry (cleanup instead)
        self.retry_policies[ErrorType.MEMORY_ERROR] = RetryPolicy(
            max_attempts=1,
            initial_delay=0.0,
            max_delay=0.0,
        )

        # Data errors - no retry (data issue)
        self.retry_policies[ErrorType.DATA_ERROR] = RetryPolicy(
            max_attempts=1,
            initial_delay=0.0,
            max_delay=0.0,
        )

        # Unknown errors - conservative retry
        self.retry_policies[ErrorType.UNKNOWN_ERROR] = RetryPolicy(
            max_attempts=2,
            initial_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True,
        )

    def execute_with_recovery(
        self,
        func: Callable,
        service_name: str,
        error_type: ErrorType = ErrorType.UNKNOWN_ERROR,
        fallback: Optional[Callable] = None,
        context: Optional[Dict] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with full recovery strategy.

        Args:
            func: Function to execute
            service_name: Service identifier ('ollama', 'fastf1', 'modal')
            error_type: Type of error expected
            fallback: Optional fallback function if all retries fail
            context: Additional context for error tracking
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result from function or fallback

        Raises:
            Exception: If recovery fails and no fallback provided
        """
        retry_policy = self.retry_policies.get(error_type, self.retry_policies[ErrorType.UNKNOWN_ERROR])
        circuit_breaker = self.circuit_breakers.get(service_name)

        last_error = None

        for attempt in range(retry_policy.max_attempts):
            try:
                # Check circuit breaker
                if circuit_breaker:
                    try:
                        return circuit_breaker.call(func, *args, **kwargs)
                    except CircuitBreakerOpenError as e:
                        self.recovery_stats['circuit_breaker_blocks'] += 1
                        logger.warning(f"Circuit breaker blocked call: {e}")

                        # Try fallback immediately
                        if fallback:
                            return self._execute_fallback(fallback, context)
                        raise
                else:
                    # No circuit breaker, execute directly
                    return func(*args, **kwargs)

            except Exception as e:
                last_error = e
                self.recovery_stats['total_retries'] += 1

                # Log error
                logger.warning(
                    f"Attempt {attempt + 1}/{retry_policy.max_attempts} failed for {service_name}: "
                    f"{type(e).__name__}: {str(e)}"
                )

                # Track error
                if self.error_tracker:
                    self.error_tracker.capture_exception(
                        e,
                        context={
                            'service': service_name,
                            'attempt': attempt + 1,
                            'max_attempts': retry_policy.max_attempts,
                            **(context or {})
                        }
                    )

                # Check if we should retry
                if attempt < retry_policy.max_attempts - 1:
                    # Calculate delay
                    delay = self._calculate_backoff(
                        attempt,
                        retry_policy.initial_delay,
                        retry_policy.max_delay,
                        retry_policy.exponential_base,
                        retry_policy.jitter
                    )

                    logger.info(f"Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    # Out of retries
                    self.recovery_stats['failed_retries'] += 1
                    logger.error(f"All retries exhausted for {service_name}")

        # All retries failed, try fallback
        if fallback:
            return self._execute_fallback(fallback, context)

        # No fallback, raise last error
        raise last_error

    def _calculate_backoff(
        self,
        attempt: int,
        initial_delay: float,
        max_delay: float,
        base: float,
        jitter: bool
    ) -> float:
        """Calculate exponential backoff delay with optional jitter"""
        delay = min(initial_delay * (base ** attempt), max_delay)

        if jitter:
            # Add random jitter (±25%)
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(0, delay)

    def _execute_fallback(self, fallback: Callable, context: Optional[Dict]) -> Any:
        """Execute fallback function"""
        self.recovery_stats['graceful_degradations'] += 1

        logger.info("Executing fallback strategy")

        try:
            return fallback(context) if context else fallback()
        except Exception as e:
            logger.error(f"Fallback also failed: {e}")
            raise

    def handle_memory_error(self, threshold_mb: int = 300) -> bool:
        """
        Handle memory errors with aggressive cleanup.

        Args:
            threshold_mb: Memory threshold in MB

        Returns:
            True if cleanup was successful
        """
        try:
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)

            if memory_mb > threshold_mb:
                logger.warning(
                    f"Memory threshold exceeded: {memory_mb:.1f}MB > {threshold_mb}MB. "
                    "Triggering cleanup..."
                )

                # Force garbage collection
                collected = gc.collect()

                # Clear matplotlib figures
                try:
                    import matplotlib.pyplot as plt
                    plt.close('all')
                except ImportError:
                    pass

                self.recovery_stats['memory_cleanups'] += 1

                # Check memory after cleanup
                memory_after = process.memory_info().rss / (1024 * 1024)
                freed = memory_mb - memory_after

                logger.info(
                    f"Memory cleanup complete: "
                    f"freed {freed:.1f}MB, {collected} objects collected"
                )

                return True

            return False

        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
            return False

    def get_recovery_stats(self) -> Dict:
        """Get recovery statistics"""
        stats = self.recovery_stats.copy()

        # Add circuit breaker states
        stats['circuit_breakers'] = {
            name: cb.get_state()
            for name, cb in self.circuit_breakers.items()
        }

        # Add retry success rate
        total = stats['total_retries']
        if total > 0:
            stats['retry_success_rate'] = stats['successful_retries'] / total
        else:
            stats['retry_success_rate'] = 0.0

        return stats

    def reset_circuit_breaker(self, service_name: str):
        """Manually reset a circuit breaker (admin function)"""
        if service_name in self.circuit_breakers:
            self.circuit_breakers[service_name].reset()
            logger.info(f"Reset circuit breaker for {service_name}")
        else:
            logger.warning(f"Circuit breaker not found: {service_name}")

    def reset_all_circuit_breakers(self):
        """Reset all circuit breakers (admin function)"""
        for cb in self.circuit_breakers.values():
            cb.reset()
        logger.info("All circuit breakers reset")


# Decorator for easy recovery
def with_recovery(
    service_name: str,
    error_type: ErrorType = ErrorType.UNKNOWN_ERROR,
    fallback: Optional[Callable] = None
):
    """
    Decorator to add recovery to any function.

    Usage:
        @with_recovery('ollama', ErrorType.API_ERROR, fallback=lambda: "Fallback response")
        def call_ollama_api():
            # ... API call
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            recovery_manager = get_recovery_manager()
            return recovery_manager.execute_with_recovery(
                func,
                service_name,
                error_type,
                fallback,
                context={'function': func.__name__},
                *args,
                **kwargs
            )
        return wrapper
    return decorator


# Specific recovery strategies for each service

def recover_ollama_error(error: Exception, context: Optional[Dict] = None) -> Dict:
    """
    Recovery strategy for Ollama API errors.

    Returns:
        Fallback response with error message
    """
    logger.info("Using Ollama fallback response")

    return {
        "response": (
            "⚠️ AI analysis temporarily unavailable. "
            "The telemetry data shows interesting patterns in this section. "
            "Please try again in a moment."
        ),
        "model": "fallback",
        "done": True,
        "context_used": bool(context),
    }


def recover_fastf1_error(error: Exception, context: Optional[Dict] = None) -> Optional[object]:
    """
    Recovery strategy for FastF1 errors.

    Args:
        error: The FastF1 error
        context: Context containing session manager for cache lookup

    Returns:
        Cached session if available, None otherwise
    """
    logger.info("Attempting FastF1 cache fallback")

    if context and 'session_manager' in context:
        session_manager = context['session_manager']
        cache_key = context.get('cache_key')

        if cache_key:
            # Try to get from cache
            with session_manager._cache_lock:
                cached = session_manager._session_cache.get(cache_key)
                if cached:
                    logger.info("Successfully recovered from cache")
                    return cached

    logger.warning("No cached data available for recovery")
    return None


def recover_plot_generation_error(error: Exception, context: Optional[Dict] = None) -> bytes:
    """
    Recovery strategy for plot generation errors.

    Returns:
        Minimal error plot as bytes
    """
    logger.info("Generating fallback error plot")

    try:
        import matplotlib.pyplot as plt
        from io import BytesIO

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(
            0.5, 0.5,
            "Plot generation failed\n\nPlease try again",
            ha='center', va='center',
            fontsize=16,
            color='red'
        )
        ax.axis('off')

        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', facecolor='#1a1a1a')
        plt.close(fig)
        buffer.seek(0)

        return buffer.getvalue()

    except Exception as e:
        logger.error(f"Fallback plot generation also failed: {e}")
        raise


# Utility function to classify errors

def classify_error(error: Exception) -> ErrorType:
    """
    Classify an exception into an ErrorType.

    Args:
        error: The exception to classify

    Returns:
        ErrorType classification
    """
    error_type_name = type(error).__name__.lower()
    error_message = str(error).lower()

    # Network errors
    if any(keyword in error_type_name for keyword in ['connection', 'network', 'socket']):
        return ErrorType.NETWORK_ERROR
    if any(keyword in error_message for keyword in ['connection refused', 'network', 'unreachable']):
        return ErrorType.NETWORK_ERROR

    # Timeout errors
    if 'timeout' in error_type_name or 'timeout' in error_message:
        return ErrorType.TIMEOUT_ERROR

    # Memory errors
    if any(keyword in error_type_name for keyword in ['memory', 'memoryerror']):
        return ErrorType.MEMORY_ERROR
    if 'out of memory' in error_message:
        return ErrorType.MEMORY_ERROR

    # API errors
    if any(keyword in error_type_name for keyword in ['http', 'api', 'request']):
        return ErrorType.API_ERROR
    if any(code in error_message for code in ['500', '502', '503', '504']):
        return ErrorType.API_ERROR

    # Data errors
    if any(keyword in error_type_name for keyword in ['value', 'key', 'attribute', 'index']):
        return ErrorType.DATA_ERROR
    if 'not found' in error_message or 'missing' in error_message:
        return ErrorType.DATA_ERROR

    return ErrorType.UNKNOWN_ERROR


# Global recovery manager instance
_recovery_manager = None


def get_recovery_manager(error_tracker=None) -> RecoveryManager:
    """Get or create global recovery manager instance"""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = RecoveryManager(error_tracker)
    return _recovery_manager
