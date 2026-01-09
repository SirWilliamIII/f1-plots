"""
Error Tracking Middleware

Provides automatic error capture, request/response logging, and performance monitoring.
"""

import time
import uuid
import logging
from flask import request, g
from app.error_tracking.error_tracker import get_error_tracker, ErrorSeverity

logger = logging.getLogger(__name__)


def register_error_middleware(app):
    """Register error tracking middleware"""

    @app.before_request
    def before_request():
        """
        Execute before each request:
        - Generate request ID
        - Start performance timer
        - Log request details
        """
        # Generate unique request ID
        g.request_id = str(uuid.uuid4())
        g.request_start_time = time.time()

        # Log request
        logger.info(
            f"[{g.request_id[:8]}] {request.method} {request.path}",
            extra={
                'request_id': g.request_id,
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'user_agent': request.user_agent.string
            }
        )

    @app.after_request
    def after_request(response):
        """
        Execute after each request:
        - Log response details
        - Track performance metrics
        - Capture slow requests
        """
        # Calculate request duration
        duration = time.time() - g.get('request_start_time', time.time())
        request_id = g.get('request_id', 'unknown')

        # Log response
        logger.info(
            f"[{request_id[:8]}] {response.status_code} - {duration:.3f}s",
            extra={
                'request_id': request_id,
                'status_code': response.status_code,
                'duration': duration,
                'content_length': response.content_length
            }
        )

        # Track slow requests (> 5 seconds)
        if duration > 5.0:
            error_tracker = get_error_tracker()
            error_tracker.capture_message(
                f"Slow request detected: {request.method} {request.path} took {duration:.2f}s",
                level=ErrorSeverity.WARNING,
                context={
                    'request_id': request_id,
                    'method': request.method,
                    'path': request.path,
                    'duration': duration,
                    'endpoint': request.endpoint
                }
            )

        # Add request ID to response headers for tracing
        response.headers['X-Request-ID'] = request_id

        return response

    @app.teardown_request
    def teardown_request(exception=None):
        """
        Execute after request processing (even if exception occurred):
        - Capture any exceptions that weren't caught
        - Clean up resources
        """
        if exception is not None:
            request_id = g.get('request_id', 'unknown')

            # This exception should have been caught by error handlers
            # but we log it here for completeness
            logger.error(
                f"[{request_id[:8]}] Teardown exception: {str(exception)}",
                exc_info=True
            )

    logger.info("Error tracking middleware registered")
