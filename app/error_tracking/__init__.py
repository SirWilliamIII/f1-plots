"""
Error Tracking Module

Comprehensive error tracking, monitoring, and structured logging system
for the F1 telemetry application.

Usage:
    # Structured logging
    from app.error_tracking import get_logger
    logger = get_logger(__name__)
    logger.info("Processing request", driver="VER", session="Q")

    # Error tracking
    from app.error_tracking import get_error_tracker
    tracker = get_error_tracker()
    tracker.capture_exception(e, context={"request": request_data})

    # Audit logging
    from app.error_tracking import AuditAction
    logger.audit(AuditAction.CACHE_CLEAR, resource="session_cache")
"""

from .error_tracker import (
    ErrorTracker,
    ErrorEvent,
    ErrorSeverity,
    get_error_tracker,
)

from .structured_logger import (
    # Core classes
    StructuredLogger,
    BoundLogger,
    RequestContext,
    RequestContextManager,

    # Enums
    LogLevel,
    AuditAction,

    # Formatters
    JSONFormatter,
    HumanReadableFormatter,

    # Factory functions
    get_logger,
    get_logger_with_tracker,
    configure_logging,

    # Context management
    get_request_context,
    set_request_context,
    clear_request_context,

    # Flask integration
    init_flask_logging,

    # Utilities
    log_api_call,
)

from .recovery_manager import (
    RecoveryManager,
    CircuitState,
    ErrorType,
    RetryPolicy,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    with_recovery,
    classify_error,
    recover_ollama_error,
    recover_fastf1_error,
    recover_plot_generation_error,
    get_recovery_manager
)

__all__ = [
    # Error tracking
    'ErrorTracker',
    'ErrorEvent',
    'ErrorSeverity',
    'get_error_tracker',

    # Structured logging
    'StructuredLogger',
    'BoundLogger',
    'RequestContext',
    'RequestContextManager',
    'LogLevel',
    'AuditAction',
    'JSONFormatter',
    'HumanReadableFormatter',
    'get_logger',
    'get_logger_with_tracker',
    'configure_logging',
    'get_request_context',
    'set_request_context',
    'clear_request_context',
    'init_flask_logging',
    'log_api_call',

    # Recovery management
    'RecoveryManager',
    'CircuitState',
    'ErrorType',
    'RetryPolicy',
    'CircuitBreakerConfig',
    'CircuitBreakerOpenError',
    'with_recovery',
    'classify_error',
    'recover_ollama_error',
    'recover_fastf1_error',
    'recover_plot_generation_error',
    'get_recovery_manager',
]
