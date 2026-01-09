"""
Error Dashboard Routes

Provides web dashboard for error tracking and monitoring.
Extends the existing monitoring routes with visual dashboard.
"""

import logging
from datetime import datetime, timedelta
from flask import request, jsonify, render_template
from app.error_tracking.error_tracker import get_error_tracker, ErrorSeverity
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY

logger = logging.getLogger(__name__)


def register_error_dashboard_routes(app):
    """Register error dashboard routes (extends existing monitoring routes)"""

    @app.route("/errors/dashboard", methods=["GET"])
    def error_dashboard():
        """Render error monitoring dashboard"""
        try:
            tracker = get_error_tracker()
            stats = tracker.get_error_stats()

            # Calculate error rate
            recent_errors = [
                e for e in tracker.error_queue
                if _is_recent(e.timestamp, minutes=60)
            ]
            error_rate = len(recent_errors) / 60.0 if recent_errors else 0.0

            # Get recent errors for display
            recent = tracker.get_recent_errors(limit=50)
            recent_display = [{
                "timestamp": _format_timestamp(e.timestamp),
                "level": e.level,
                "error_type": e.error_type,
                "message": e.message[:100] + "..." if len(e.message) > 100 else e.message,
                "fingerprint": e.fingerprint
            } for e in recent]

            return render_template(
                "error_dashboard.html",
                total_errors=stats["total_errors"],
                total_warnings=stats["total_warnings"],
                suppressed_errors=stats["suppressed_errors"],
                unique_groups=stats["unique_error_groups"],
                error_rate=round(error_rate, 2),
                top_errors=stats["top_errors"],
                recent_errors=recent_display
            )

        except Exception as e:
            logger.error(f"Failed to render dashboard: {e}")
            return render_template("error.html", error_message="Failed to load error dashboard"), 500

    @app.route("/api/errors/stats", methods=["GET"])
    def get_error_stats_for_dashboard():
        """Get error statistics including trends for dashboard visualization"""
        with REQUEST_LATENCY.labels(method="GET", endpoint="/api/errors/stats").time():
            try:
                tracker = get_error_tracker()
                stats = tracker.get_error_stats()

                # Calculate error rate (errors per minute over last hour)
                recent_errors = [
                    e for e in tracker.error_queue
                    if _is_recent(e.timestamp, minutes=60)
                ]
                error_rate = len(recent_errors) / 60.0 if recent_errors else 0.0

                # Group errors by time buckets for trend visualization
                error_trends = _calculate_error_trends(tracker.error_queue)

                response = {
                    "total_errors": stats["total_errors"],
                    "total_warnings": stats["total_warnings"],
                    "suppressed_errors": stats["suppressed_errors"],
                    "unique_error_groups": stats["unique_error_groups"],
                    "error_rate": round(error_rate, 2),
                    "top_errors": stats["top_errors"],
                    "trends": error_trends,
                    "timestamp": datetime.utcnow().isoformat()
                }

                return jsonify(response), 200

            except Exception as e:
                logger.error(f"Failed to get error stats: {e}")
                return jsonify({"error": "Failed to retrieve error statistics"}), 500

    @app.route("/monitoring/errors", methods=["GET"])
    def get_error_stats():
        """
        Get comprehensive error statistics

        Returns error counts, top errors, and overall system health metrics.
        """
        try:
            error_tracker = get_error_tracker()
            stats = error_tracker.get_error_stats()

            return jsonify({
                "status": "success",
                "data": stats
            })
        except Exception as e:
            logger.error(f"Failed to get error stats: {e}")
            return jsonify({
                "status": "error",
                "message": "Failed to retrieve error statistics"
            }), 500

    @app.route("/monitoring/errors/recent", methods=["GET"])
    def get_recent_errors():
        """
        Get recent errors

        Query parameters:
        - limit: Number of recent errors to return (default: 50, max: 500)
        """
        try:
            limit = min(int(request.args.get("limit", 50)), 500)

            error_tracker = get_error_tracker()
            recent_errors = error_tracker.get_recent_errors(limit)

            # Convert ErrorEvent objects to dicts
            errors_data = [error.to_dict() for error in recent_errors]

            return jsonify({
                "status": "success",
                "data": {
                    "errors": errors_data,
                    "count": len(errors_data)
                }
            })
        except Exception as e:
            logger.error(f"Failed to get recent errors: {e}")
            return jsonify({
                "status": "error",
                "message": "Failed to retrieve recent errors"
            }), 500

    @app.route("/monitoring/errors/group/<fingerprint>", methods=["GET"])
    def get_error_group(fingerprint):
        """
        Get details for a specific error group

        Path parameters:
        - fingerprint: Error fingerprint ID
        """
        try:
            error_tracker = get_error_tracker()
            error_group = error_tracker.get_error_group(fingerprint)

            if not error_group:
                return jsonify({
                    "status": "error",
                    "message": f"Error group not found: {fingerprint}"
                }), 404

            return jsonify({
                "status": "success",
                "data": error_group
            })
        except Exception as e:
            logger.error(f"Failed to get error group {fingerprint}: {e}")
            return jsonify({
                "status": "error",
                "message": "Failed to retrieve error group"
            }), 500

    @app.route("/monitoring/errors/clear", methods=["POST"])
    def clear_errors():
        """
        Clear error tracking data (for testing/maintenance)

        WARNING: This will clear all error history!
        """
        try:
            error_tracker = get_error_tracker()
            error_tracker.clear_errors()

            logger.info("Error tracking data cleared")

            return jsonify({
                "status": "success",
                "message": "Error tracking data cleared"
            })
        except Exception as e:
            logger.error(f"Failed to clear errors: {e}")
            return jsonify({
                "status": "error",
                "message": "Failed to clear error data"
            }), 500

    @app.route("/monitoring/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint

        Returns system health including error rates and recent issues.
        """
        try:
            error_tracker = get_error_tracker()
            stats = error_tracker.get_error_stats()

            # Determine health status based on error rates
            health_status = "healthy"
            issues = []

            # Check for high error rate
            if stats.get('total_errors', 0) > 100:
                health_status = "degraded"
                issues.append("High error count detected")

            # Check for fatal errors
            recent_errors = error_tracker.get_recent_errors(10)
            fatal_count = sum(1 for e in recent_errors if e.level == "fatal")
            if fatal_count > 0:
                health_status = "unhealthy"
                issues.append(f"{fatal_count} fatal errors in recent history")

            return jsonify({
                "status": health_status,
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": {
                    "total_errors": stats.get('total_errors', 0),
                    "total_warnings": stats.get('total_warnings', 0),
                    "suppressed_errors": stats.get('suppressed_errors', 0),
                    "unique_error_groups": stats.get('unique_error_groups', 0)
                },
                "issues": issues
            })
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                "status": "unhealthy",
                "message": "Health check failed",
                "error": str(e)
            }), 500

    logger.info("Error dashboard routes registered")


def _is_recent(timestamp_str: str, minutes: int = 60) -> bool:
    """Check if timestamp is within the last N minutes"""
    try:
        timestamp = datetime.fromisoformat(timestamp_str)
        age = datetime.utcnow() - timestamp
        return age.total_seconds() <= (minutes * 60)
    except Exception:
        return False


def _format_timestamp(timestamp_str: str) -> str:
    """Format timestamp for display"""
    try:
        timestamp = datetime.fromisoformat(timestamp_str)
        now = datetime.utcnow()
        delta = now - timestamp

        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())}s ago"
        elif delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)}m ago"
        elif delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() / 3600)}h ago"
        else:
            return timestamp.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return timestamp_str


def _calculate_error_trends(error_queue, buckets: int = 12) -> list:
    """
    Calculate error trends over time for visualization.
    Returns list of time buckets with error counts.
    """
    try:
        if not error_queue:
            return []

        now = datetime.utcnow()
        bucket_size = 5  # 5 minutes per bucket
        trends = []

        for i in range(buckets):
            bucket_start = now - timedelta(minutes=(i + 1) * bucket_size)
            bucket_end = now - timedelta(minutes=i * bucket_size)

            # Count errors in this time bucket
            count = sum(
                1 for e in error_queue
                if bucket_start <= datetime.fromisoformat(e.timestamp) < bucket_end
            )

            trends.insert(0, {
                "time": bucket_end.strftime("%H:%M"),
                "count": count
            })

        return trends

    except Exception as e:
        logger.error(f"Failed to calculate error trends: {e}")
        return []
