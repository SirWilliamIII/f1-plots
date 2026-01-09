"""
Error Tracking Service

Captures, groups, and reports errors with intelligent deduplication and alerting.
"""

import time
import traceback
import hashlib
import json
import os
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


@dataclass
class ErrorEvent:
    """Structured error event"""
    timestamp: str
    level: str
    message: str
    error_type: str
    stack_trace: Optional[str]
    fingerprint: str
    context: Dict[str, Any]

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


class ErrorTracker:
    """
    Central error tracking service with intelligent grouping and alerting.

    Features:
    - Error grouping by fingerprint
    - Rate limiting for duplicate errors
    - Contextual error enrichment
    - Integration hooks for external services (Sentry, etc.)
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.error_groups: Dict[str, Dict] = {}
        self.error_queue: List[ErrorEvent] = []
        self.lock = Lock()

        # Configuration
        self.max_queue_size = self.config.get('max_queue_size', 1000)
        self.rate_limit_window = self.config.get('rate_limit_window', 60)  # seconds
        self.max_errors_per_window = self.config.get('max_errors_per_window', 10)

        # Stats
        self.total_errors = 0
        self.total_warnings = 0
        self.suppressed_errors = 0

        logger.info("ErrorTracker initialized")

    def capture_exception(
        self,
        error: Exception,
        context: Optional[Dict] = None,
        level: ErrorSeverity = ErrorSeverity.ERROR
    ) -> str:
        """
        Capture an exception with context.

        Args:
            error: The exception to capture
            context: Additional context (request data, user info, etc.)
            level: Severity level

        Returns:
            Fingerprint of the error
        """
        # Build error event
        error_type = type(error).__name__
        message = str(error)
        stack_trace = traceback.format_exc()

        # Generate fingerprint
        fingerprint = self._generate_fingerprint(error_type, message, stack_trace)

        # Build event
        event = ErrorEvent(
            timestamp=datetime.utcnow().isoformat(),
            level=level.value,
            message=message,
            error_type=error_type,
            stack_trace=stack_trace,
            fingerprint=fingerprint,
            context=self._enrich_context(context or {})
        )

        # Check rate limiting
        if self._should_suppress(fingerprint):
            self.suppressed_errors += 1
            logger.debug(f"Suppressed duplicate error: {fingerprint}")
            return fingerprint

        # Add to queue
        with self.lock:
            self._add_to_group(event)
            self.error_queue.append(event)

            # Trim queue if needed
            if len(self.error_queue) > self.max_queue_size:
                self.error_queue = self.error_queue[-self.max_queue_size:]

            # Update stats
            if level == ErrorSeverity.ERROR or level == ErrorSeverity.FATAL:
                self.total_errors += 1
            elif level == ErrorSeverity.WARNING:
                self.total_warnings += 1

        # Log the error
        logger.error(
            f"Error captured: {error_type} - {message}",
            extra={
                'fingerprint': fingerprint,
                'context': event.context
            }
        )

        # Check if we should alert
        self._check_alert_conditions(event)

        return fingerprint

    def capture_message(
        self,
        message: str,
        level: ErrorSeverity = ErrorSeverity.INFO,
        context: Optional[Dict] = None
    ) -> str:
        """Capture a message (not an exception)"""
        fingerprint = hashlib.sha256(message.encode()).hexdigest()[:16]

        event = ErrorEvent(
            timestamp=datetime.utcnow().isoformat(),
            level=level.value,
            message=message,
            error_type="Message",
            stack_trace=None,
            fingerprint=fingerprint,
            context=self._enrich_context(context or {})
        )

        with self.lock:
            self.error_queue.append(event)
            if len(self.error_queue) > self.max_queue_size:
                self.error_queue = self.error_queue[-self.max_queue_size:]

        return fingerprint

    def _generate_fingerprint(self, error_type: str, message: str, stack_trace: str) -> str:
        """Generate unique fingerprint for error grouping"""
        # Normalize message (remove numbers, IDs, etc.)
        import re
        normalized_message = re.sub(r'\d+', '<N>', message)
        normalized_message = re.sub(r'0x[0-9a-fA-F]+', '<ADDR>', normalized_message)

        # Extract location from stack trace
        location = self._extract_location(stack_trace)

        # Generate hash
        components = f"{error_type}|{normalized_message}|{location}"
        fingerprint = hashlib.sha256(components.encode()).hexdigest()[:16]

        return fingerprint

    def _extract_location(self, stack_trace: str) -> str:
        """Extract error location from stack trace"""
        if not stack_trace:
            return "unknown"

        lines = stack_trace.split('\n')
        for line in lines:
            if 'File "' in line and '/app/' in line:
                # Extract app-specific file and line
                import re
                match = re.search(r'File ".*/(app/.*\.py)", line (\d+)', line)
                if match:
                    return f"{match.group(1)}:{match.group(2)}"

        return "unknown"

    def _enrich_context(self, context: Dict) -> Dict:
        """Add system context to error"""
        enriched = context.copy()
        enriched.update({
            'environment': os.getenv('FLASK_ENV', 'unknown'),
            'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown',
            'process_id': os.getpid(),
        })
        return enriched

    def _add_to_group(self, event: ErrorEvent):
        """Add error to its group"""
        fingerprint = event.fingerprint

        if fingerprint not in self.error_groups:
            self.error_groups[fingerprint] = {
                'fingerprint': fingerprint,
                'first_seen': event.timestamp,
                'last_seen': event.timestamp,
                'count': 0,
                'error_type': event.error_type,
                'message': event.message,
                'level': event.level,
                'occurrences': []
            }

        group = self.error_groups[fingerprint]
        group['count'] += 1
        group['last_seen'] = event.timestamp
        group['occurrences'].append({
            'timestamp': event.timestamp,
            'context': event.context
        })

        # Keep only last 10 occurrences per group
        if len(group['occurrences']) > 10:
            group['occurrences'] = group['occurrences'][-10:]

    def _should_suppress(self, fingerprint: str) -> bool:
        """Check if error should be suppressed due to rate limiting"""
        if fingerprint not in self.error_groups:
            return False

        group = self.error_groups[fingerprint]

        # Count recent occurrences
        now = datetime.utcnow()
        recent_count = 0

        for occurrence in group.get('occurrences', []):
            occurrence_time = datetime.fromisoformat(occurrence['timestamp'])
            age = (now - occurrence_time).total_seconds()

            if age <= self.rate_limit_window:
                recent_count += 1

        return recent_count >= self.max_errors_per_window

    def _check_alert_conditions(self, event: ErrorEvent):
        """Check if error should trigger an alert"""
        # Fatal errors always alert
        if event.level == ErrorSeverity.FATAL.value:
            self._send_alert(event, "FATAL ERROR")
            return

        # Check if error group has exceeded threshold
        group = self.error_groups.get(event.fingerprint)
        if group and group['count'] >= 10:
            self._send_alert(event, f"High error frequency: {group['count']} occurrences")

    def _send_alert(self, event: ErrorEvent, reason: str):
        """Send alert (can be extended to integrate with Slack, PagerDuty, etc.)"""
        logger.critical(
            f"ALERT: {reason} - {event.error_type}: {event.message}",
            extra={'fingerprint': event.fingerprint}
        )

        # TODO: Integrate with external alerting services
        # - Slack webhook
        # - PagerDuty
        # - Email

    def get_error_stats(self) -> Dict:
        """Get error statistics"""
        with self.lock:
            return {
                'total_errors': self.total_errors,
                'total_warnings': self.total_warnings,
                'suppressed_errors': self.suppressed_errors,
                'unique_error_groups': len(self.error_groups),
                'queue_size': len(self.error_queue),
                'top_errors': self._get_top_errors(5)
            }

    def _get_top_errors(self, limit: int = 5) -> List[Dict]:
        """Get top N most frequent errors"""
        sorted_groups = sorted(
            self.error_groups.values(),
            key=lambda x: x['count'],
            reverse=True
        )

        return [{
            'fingerprint': g['fingerprint'],
            'error_type': g['error_type'],
            'message': g['message'],
            'count': g['count'],
            'first_seen': g['first_seen'],
            'last_seen': g['last_seen']
        } for g in sorted_groups[:limit]]

    def get_error_group(self, fingerprint: str) -> Optional[Dict]:
        """Get details for a specific error group"""
        with self.lock:
            return self.error_groups.get(fingerprint)

    def get_recent_errors(self, limit: int = 50) -> List[ErrorEvent]:
        """Get recent errors"""
        with self.lock:
            return self.error_queue[-limit:]

    def clear_errors(self):
        """Clear error queue and reset stats (for testing)"""
        with self.lock:
            self.error_queue.clear()
            self.error_groups.clear()
            self.total_errors = 0
            self.total_warnings = 0
            self.suppressed_errors = 0


# Global error tracker instance
_error_tracker = None


def get_error_tracker(config: Optional[Dict] = None) -> ErrorTracker:
    """Get or create global error tracker instance"""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker(config)
    return _error_tracker
