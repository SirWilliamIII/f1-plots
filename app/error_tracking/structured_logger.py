"""
Structured Logging System for F1 Telemetry Application

Provides JSON-formatted logs for production and human-readable logs for development,
with contextual metadata injection, performance timing, and audit logging capabilities.

Usage:
    from app.error_tracking import get_logger
    logger = get_logger(__name__)

    logger.info("Processing request", extra={"driver": "VER", "session": "Q"})

    with logger.timed("plot_generation"):
        generate_plot()
"""

from __future__ import annotations

import functools
import json
import logging
import os
import socket
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
    ParamSpec,
)

# Type variables for decorator typing
P = ParamSpec('P')
T = TypeVar('T')


class LogLevel(Enum):
    """Standard log levels with numeric values for comparison."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    @classmethod
    def from_string(cls, level: str) -> 'LogLevel':
        """Convert string to LogLevel enum."""
        level_upper = level.upper()
        if level_upper in cls.__members__:
            return cls[level_upper]
        return cls.INFO


class AuditAction(Enum):
    """Audit action types for sensitive operations."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    ACCESS = "access"
    AUTHENTICATE = "authenticate"
    AUTHORIZE = "authorize"
    EXPORT = "export"
    CACHE_CLEAR = "cache_clear"
    CONFIG_CHANGE = "config_change"


@dataclass
class RequestContext:
    """
    Thread-local request context for tracking request metadata.

    Attributes:
        request_id: Unique identifier for the request
        session_id: User session identifier (if available)
        user_id: User identifier (if authenticated)
        ip_address: Client IP address
        user_agent: Client user agent string
        path: Request path
        method: HTTP method
        start_time: Request start timestamp
        extra: Additional context data
    """
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary, excluding None values."""
        result = {}
        for key, value in asdict(self).items():
            if value is not None and key != 'extra':
                result[key] = value
        if self.extra:
            result.update(self.extra)
        return result

    def elapsed_ms(self) -> float:
        """Get elapsed time since request start in milliseconds."""
        return (time.time() - self.start_time) * 1000


class RequestContextManager:
    """
    Thread-local storage manager for request context.

    Provides a way to store and retrieve request-specific context
    across the application without explicit parameter passing.

    Usage:
        context_manager = RequestContextManager()

        # Set context at request start
        context_manager.set_context(RequestContext(
            request_id="abc-123",
            path="/api/plot"
        ))

        # Access context anywhere in the request
        ctx = context_manager.get_context()
        print(ctx.request_id)

        # Clear at request end
        context_manager.clear_context()
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def set_context(self, context: RequestContext) -> None:
        """Set the request context for the current thread."""
        self._local.context = context

    def get_context(self) -> Optional[RequestContext]:
        """Get the request context for the current thread."""
        return getattr(self._local, 'context', None)

    def clear_context(self) -> None:
        """Clear the request context for the current thread."""
        if hasattr(self._local, 'context'):
            delattr(self._local, 'context')

    @contextmanager
    def request_scope(self, context: Optional[RequestContext] = None):
        """
        Context manager for request scope.

        Usage:
            with context_manager.request_scope(RequestContext(...)):
                # Context is available here
                process_request()
            # Context is automatically cleared
        """
        if context is None:
            context = RequestContext()

        self.set_context(context)
        try:
            yield context
        finally:
            self.clear_context()


# Global request context manager instance
_request_context = RequestContextManager()


def get_request_context() -> Optional[RequestContext]:
    """Get the current request context (convenience function)."""
    return _request_context.get_context()


def set_request_context(context: RequestContext) -> None:
    """Set the current request context (convenience function)."""
    _request_context.set_context(context)


def clear_request_context() -> None:
    """Clear the current request context (convenience function)."""
    _request_context.clear_context()


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for production environments.

    Outputs structured JSON logs that can be easily parsed by log
    aggregation systems like Elasticsearch, Splunk, or CloudWatch.

    Output format:
    {
        "timestamp": "2024-01-15T10:30:45.123456Z",
        "level": "INFO",
        "logger": "app.routes.plot_routes",
        "message": "Plot generated successfully",
        "request_id": "abc-123",
        "environment": "production",
        "hostname": "server-1",
        "process_id": 12345,
        "thread_id": 140123456789,
        "extra_field": "value"
    }
    """

    # Fields to exclude from extra data (already handled explicitly)
    RESERVED_ATTRS = frozenset({
        'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
        'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
        'message', 'msg', 'name', 'pathname', 'process', 'processName',
        'relativeCreated', 'stack_info', 'thread', 'threadName', 'taskName',
    })

    def __init__(
        self,
        include_stack_trace: bool = True,
        include_source_location: bool = True,
    ) -> None:
        super().__init__()
        self.include_stack_trace = include_stack_trace
        self.include_source_location = include_source_location
        self._hostname = self._get_hostname()
        self._environment = os.getenv('FLASK_ENV', 'unknown')

    def _get_hostname(self) -> str:
        """Get the hostname safely."""
        try:
            return socket.gethostname()
        except Exception:
            return 'unknown'

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        # Base log entry
        log_entry: Dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add system context
        log_entry['environment'] = self._environment
        log_entry['hostname'] = self._hostname
        log_entry['process_id'] = record.process
        log_entry['thread_id'] = record.thread

        # Add request context if available
        request_ctx = get_request_context()
        if request_ctx:
            log_entry['request_id'] = request_ctx.request_id
            if request_ctx.session_id:
                log_entry['session_id'] = request_ctx.session_id
            if request_ctx.user_id:
                log_entry['user_id'] = request_ctx.user_id
            if request_ctx.path:
                log_entry['path'] = request_ctx.path
            if request_ctx.method:
                log_entry['method'] = request_ctx.method

        # Add source location
        if self.include_source_location:
            log_entry['source'] = {
                'file': record.pathname,
                'line': record.lineno,
                'function': record.funcName,
            }

        # Add exception info
        if record.exc_info and self.include_stack_trace:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in self.RESERVED_ATTRS and not key.startswith('_'):
                try:
                    # Ensure value is JSON serializable
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        return json.dumps(log_entry, default=str)


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable log formatter for development environments.

    Provides colorized, easy-to-read logs for local development.

    Output format:
    2024-01-15 10:30:45.123 | INFO     | app.routes.plot_routes:generate_plot:42 | Plot generated successfully | request_id=abc-123 driver=VER
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[1;31m', # Bold Red
        'RESET': '\033[0m',
        'GRAY': '\033[90m',
        'BOLD': '\033[1m',
    }

    def __init__(self, use_colors: bool = True) -> None:
        super().__init__()
        self.use_colors = use_colors and self._supports_colors()

    def _supports_colors(self) -> bool:
        """Check if the terminal supports colors."""
        # Check if running in a TTY
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False

        # Check for TERM environment variable
        term = os.getenv('TERM', '')
        if 'color' in term or term in ('xterm', 'xterm-256color', 'screen'):
            return True

        return True  # Default to True for most modern terminals

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self.use_colors:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['RESET']}"

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record in human-readable format."""
        # Timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        # Level with padding and color
        level = record.levelname.ljust(8)
        if self.use_colors:
            level = self._colorize(level, record.levelname)

        # Logger name and location
        location = f"{record.name}:{record.funcName}:{record.lineno}"
        if self.use_colors:
            location = self._colorize(location, 'GRAY')

        # Message
        message = record.getMessage()

        # Build extra fields string
        extra_parts = []

        # Add request context
        request_ctx = get_request_context()
        if request_ctx:
            extra_parts.append(f"request_id={request_ctx.request_id[:8]}")

        # Add extra record fields
        for key, value in record.__dict__.items():
            if key not in JSONFormatter.RESERVED_ATTRS and not key.startswith('_'):
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + '...'
                extra_parts.append(f"{key}={value}")

        extra_str = ' | '.join(extra_parts) if extra_parts else ''
        if extra_str and self.use_colors:
            extra_str = self._colorize(extra_str, 'GRAY')

        # Build final message
        parts = [timestamp, level, location, message]
        if extra_str:
            parts.append(extra_str)

        log_line = ' | '.join(parts)

        # Add exception info
        if record.exc_info:
            log_line += '\n' + self.formatException(record.exc_info)

        return log_line


class StructuredLogger:
    """
    Enhanced logger with structured logging capabilities.

    Provides:
    - JSON-formatted logs in production
    - Human-readable logs in development
    - Contextual metadata injection
    - Performance timing
    - Audit logging
    - Integration with ErrorTracker

    Usage:
        logger = StructuredLogger(__name__)

        # Basic logging
        logger.info("Processing request", driver="VER", session="Q")

        # Performance timing
        with logger.timed("plot_generation"):
            generate_plot()

        # Audit logging
        logger.audit(AuditAction.CACHE_CLEAR, resource="session_cache")
    """

    def __init__(
        self,
        name: str,
        level: Optional[Union[str, int, LogLevel]] = None,
        error_tracker: Optional[Any] = None,
    ) -> None:
        """
        Initialize the structured logger.

        Args:
            name: Logger name (typically __name__)
            level: Log level (default: from FLASK_ENV or INFO)
            error_tracker: Optional ErrorTracker instance for error integration
        """
        self.name = name
        self._logger = logging.getLogger(name)
        self._error_tracker = error_tracker

        # Set level
        if level is None:
            env_level = os.getenv('LOG_LEVEL', 'INFO')
            level = getattr(logging, env_level.upper(), logging.INFO)
        elif isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        elif isinstance(level, LogLevel):
            level = level.value

        self._logger.setLevel(level)

    def _log(
        self,
        level: int,
        message: str,
        exc_info: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """
        Internal logging method with extra field injection.

        Args:
            level: Logging level
            message: Log message
            exc_info: Whether to include exception info
            **kwargs: Additional context to include in the log
        """
        # Merge with any existing extra data
        extra = kwargs.copy()

        self._logger.log(level, message, exc_info=exc_info, extra=extra)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a DEBUG level message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an INFO level message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a WARNING level message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(
        self,
        message: str,
        exc_info: bool = False,
        exception: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        """
        Log an ERROR level message.

        Args:
            message: Error message
            exc_info: Include exception traceback
            exception: Optional exception to track
            **kwargs: Additional context
        """
        self._log(logging.ERROR, message, exc_info=exc_info, **kwargs)

        # Integrate with error tracker if available and exception provided
        if self._error_tracker and exception:
            from .error_tracker import ErrorSeverity
            self._error_tracker.capture_exception(
                exception,
                context=kwargs,
                level=ErrorSeverity.ERROR,
            )

    def critical(
        self,
        message: str,
        exc_info: bool = True,
        exception: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        """
        Log a CRITICAL level message.

        Args:
            message: Critical error message
            exc_info: Include exception traceback (default: True)
            exception: Optional exception to track
            **kwargs: Additional context
        """
        self._log(logging.CRITICAL, message, exc_info=exc_info, **kwargs)

        # Integrate with error tracker if available
        if self._error_tracker and exception:
            from .error_tracker import ErrorSeverity
            self._error_tracker.capture_exception(
                exception,
                context=kwargs,
                level=ErrorSeverity.FATAL,
            )

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log an ERROR level message with exception info."""
        self._log(logging.ERROR, message, exc_info=True, **kwargs)

    @contextmanager
    def timed(
        self,
        operation: str,
        level: int = logging.DEBUG,
        warn_threshold_ms: Optional[float] = None,
        **kwargs: Any,
    ):
        """
        Context manager for timing operations.

        Args:
            operation: Name of the operation being timed
            level: Log level for the timing message
            warn_threshold_ms: If set, log at WARNING if duration exceeds this
            **kwargs: Additional context to include

        Usage:
            with logger.timed("plot_generation", warn_threshold_ms=5000):
                generate_plot()

        Yields:
            dict: Timing context that can be updated with additional data
        """
        context = {'operation': operation, **kwargs}
        start_time = time.perf_counter()

        self._log(level, f"Starting: {operation}", **context)

        try:
            yield context
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            context['duration_ms'] = round(duration_ms, 2)
            context['status'] = 'failed'
            context['error'] = str(e)
            self._log(logging.ERROR, f"Failed: {operation}", exc_info=True, **context)
            raise
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            context['duration_ms'] = round(duration_ms, 2)
            context['status'] = 'success'

            # Determine log level based on threshold
            log_level = level
            if warn_threshold_ms and duration_ms > warn_threshold_ms:
                log_level = logging.WARNING
                context['slow'] = True

            self._log(log_level, f"Completed: {operation}", **context)

    def timed_function(
        self,
        operation: Optional[str] = None,
        level: int = logging.DEBUG,
        warn_threshold_ms: Optional[float] = None,
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """
        Decorator for timing function execution.

        Args:
            operation: Operation name (default: function name)
            level: Log level for timing message
            warn_threshold_ms: Warn if execution exceeds this threshold

        Usage:
            @logger.timed_function(warn_threshold_ms=1000)
            def slow_operation():
                time.sleep(2)
        """
        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            op_name = operation or func.__name__

            @functools.wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                with self.timed(op_name, level=level, warn_threshold_ms=warn_threshold_ms):
                    return func(*args, **kwargs)

            return wrapper
        return decorator

    def audit(
        self,
        action: AuditAction,
        resource: str,
        resource_id: Optional[str] = None,
        outcome: str = 'success',
        **kwargs: Any,
    ) -> None:
        """
        Log an audit event for sensitive operations.

        Args:
            action: The audit action type
            resource: The resource being acted upon
            resource_id: Optional identifier for the resource
            outcome: 'success' or 'failure'
            **kwargs: Additional audit context

        Usage:
            logger.audit(
                AuditAction.CACHE_CLEAR,
                resource="session_cache",
                outcome="success",
                cleared_sessions=5
            )
        """
        audit_entry = {
            'audit': True,
            'action': action.value,
            'resource': resource,
            'outcome': outcome,
            **kwargs,
        }

        if resource_id:
            audit_entry['resource_id'] = resource_id

        # Add request context for audit trail
        request_ctx = get_request_context()
        if request_ctx:
            audit_entry['user_id'] = request_ctx.user_id
            audit_entry['ip_address'] = request_ctx.ip_address

        # Audit logs are always at INFO level or higher
        level = logging.INFO if outcome == 'success' else logging.WARNING
        self._log(
            level,
            f"AUDIT: {action.value} on {resource}",
            **audit_entry,
        )

    def bind(self, **kwargs: Any) -> 'BoundLogger':
        """
        Create a bound logger with pre-set context.

        Args:
            **kwargs: Context to bind to all log messages

        Returns:
            BoundLogger with the specified context

        Usage:
            request_logger = logger.bind(driver="VER", session="Q")
            request_logger.info("Processing lap data")  # Includes driver and session
        """
        return BoundLogger(self, kwargs)

    def set_error_tracker(self, error_tracker: Any) -> None:
        """Set the error tracker for error integration."""
        self._error_tracker = error_tracker


class BoundLogger:
    """
    A logger with pre-bound context that is included in all log messages.

    Created via StructuredLogger.bind() method.
    """

    def __init__(self, logger: StructuredLogger, context: Dict[str, Any]) -> None:
        self._logger = logger
        self._context = context

    def _merge_context(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Merge bound context with call-time kwargs."""
        merged = self._context.copy()
        merged.update(kwargs)
        return merged

    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(message, **self._merge_context(kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(message, **self._merge_context(kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(message, **self._merge_context(kwargs))

    def error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        self._logger.error(message, exc_info=exc_info, **self._merge_context(kwargs))

    def critical(self, message: str, exc_info: bool = True, **kwargs: Any) -> None:
        self._logger.critical(message, exc_info=exc_info, **self._merge_context(kwargs))

    def exception(self, message: str, **kwargs: Any) -> None:
        self._logger.exception(message, **self._merge_context(kwargs))

    def bind(self, **kwargs: Any) -> 'BoundLogger':
        """Create a new bound logger with additional context."""
        return BoundLogger(self._logger, self._merge_context(kwargs))


# Module-level logger registry for reuse
_loggers: Dict[str, StructuredLogger] = {}
_handlers_configured = False
_config_lock = threading.Lock()


def configure_logging(
    level: Optional[Union[str, int]] = None,
    json_output: Optional[bool] = None,
    include_source_location: bool = True,
) -> None:
    """
    Configure the root logging settings.

    This should be called once at application startup.

    Args:
        level: Log level (default: from LOG_LEVEL env var or INFO)
        json_output: Force JSON output (default: auto-detect from FLASK_ENV)
        include_source_location: Include file/line info in JSON logs
    """
    global _handlers_configured

    with _config_lock:
        if _handlers_configured:
            return

        # Determine log level
        if level is None:
            level = os.getenv('LOG_LEVEL', 'INFO').upper()
        if isinstance(level, str):
            level = getattr(logging, level, logging.INFO)

        # Determine output format
        if json_output is None:
            json_output = os.getenv('FLASK_ENV', 'development') == 'production'

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)

        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create appropriate handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        # Set formatter based on environment
        if json_output:
            formatter = JSONFormatter(include_source_location=include_source_location)
        else:
            formatter = HumanReadableFormatter()

        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

        _handlers_configured = True


def get_logger(
    name: str,
    level: Optional[Union[str, int, LogLevel]] = None,
) -> StructuredLogger:
    """
    Get or create a structured logger for the given module.

    This is the main entry point for obtaining loggers in the application.
    Loggers are cached and reused for the same name.

    Args:
        name: Logger name (typically __name__)
        level: Optional specific log level for this logger

    Returns:
        StructuredLogger instance

    Usage:
        from app.error_tracking import get_logger

        logger = get_logger(__name__)
        logger.info("Application started")
    """
    # Ensure logging is configured
    configure_logging()

    # Check cache
    if name in _loggers:
        return _loggers[name]

    # Create new logger
    with _config_lock:
        # Double-check after acquiring lock
        if name in _loggers:
            return _loggers[name]

        logger = StructuredLogger(name, level=level)
        _loggers[name] = logger

        return logger


def get_logger_with_tracker(
    name: str,
    error_tracker: Optional[Any] = None,
) -> StructuredLogger:
    """
    Get a structured logger with error tracker integration.

    Args:
        name: Logger name (typically __name__)
        error_tracker: ErrorTracker instance for error capture

    Returns:
        StructuredLogger with error tracker integration
    """
    logger = get_logger(name)
    if error_tracker:
        logger.set_error_tracker(error_tracker)
    return logger


# Flask integration helpers

def init_flask_logging(app) -> None:
    """
    Initialize structured logging for a Flask application.

    Should be called in the app factory function.

    Args:
        app: Flask application instance

    Usage:
        from app.error_tracking.structured_logger import init_flask_logging

        def create_app():
            app = Flask(__name__)
            init_flask_logging(app)
            return app
    """
    from flask import g, request

    # Configure logging based on Flask config
    configure_logging(
        level=app.config.get('LOG_LEVEL', 'INFO'),
        json_output=not app.debug,
    )

    logger = get_logger('flask.request')

    @app.before_request
    def before_request():
        """Set up request context before each request."""
        # Generate or extract request ID
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

        # Create request context
        ctx = RequestContext(
            request_id=request_id,
            session_id=request.cookies.get('session_id'),
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None,
            path=request.path,
            method=request.method,
        )

        # Store in thread-local and Flask's g
        set_request_context(ctx)
        g.request_context = ctx
        g.request_start_time = time.time()

        logger.debug(
            "Request started",
            path=request.path,
            method=request.method,
        )

    @app.after_request
    def after_request(response):
        """Log request completion and add request ID header."""
        ctx = get_request_context()

        if ctx:
            duration_ms = (time.time() - g.get('request_start_time', time.time())) * 1000

            # Determine log level based on status code
            if response.status_code >= 500:
                log_level = logging.ERROR
            elif response.status_code >= 400:
                log_level = logging.WARNING
            else:
                log_level = logging.INFO

            logger._log(
                log_level,
                "Request completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
                path=request.path,
                method=request.method,
            )

            # Add request ID to response headers
            response.headers['X-Request-ID'] = ctx.request_id

        return response

    @app.teardown_request
    def teardown_request(exception):
        """Clean up request context."""
        if exception:
            logger.error(
                "Request failed with exception",
                exc_info=True,
                exception=str(exception),
            )
        clear_request_context()


# Utility functions for common logging patterns

def log_api_call(
    logger: StructuredLogger,
    endpoint: str,
    method: str = 'GET',
    **kwargs: Any,
) -> Callable:
    """
    Decorator to log API calls with timing.

    Args:
        logger: StructuredLogger instance
        endpoint: API endpoint name
        method: HTTP method
        **kwargs: Additional context

    Usage:
        @log_api_call(logger, "/api/plot", method="POST")
        def generate_plot():
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **func_kwargs: P.kwargs) -> T:
            with logger.timed(
                f"API:{endpoint}",
                level=logging.INFO,
                endpoint=endpoint,
                method=method,
                **kwargs,
            ):
                return func(*args, **func_kwargs)
        return wrapper
    return decorator


# Export public API
__all__ = [
    # Core classes
    'StructuredLogger',
    'BoundLogger',
    'RequestContext',
    'RequestContextManager',

    # Enums
    'LogLevel',
    'AuditAction',

    # Formatters
    'JSONFormatter',
    'HumanReadableFormatter',

    # Factory functions
    'get_logger',
    'get_logger_with_tracker',
    'configure_logging',

    # Context management
    'get_request_context',
    'set_request_context',
    'clear_request_context',

    # Flask integration
    'init_flask_logging',

    # Utilities
    'log_api_call',
]
