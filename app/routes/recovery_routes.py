"""
Recovery Management Routes

Provides endpoints for monitoring and managing error recovery.
"""

import logging
from flask import jsonify
from app.error_tracking import get_recovery_manager

logger = logging.getLogger(__name__)


def register_recovery_routes(app):
    """Register recovery management routes"""

    @app.route("/recovery_stats", methods=["GET"])
    def recovery_stats():
        """
        Get comprehensive recovery statistics.

        Returns:
            JSON with recovery stats, circuit breaker states, and retry metrics
        """
        try:
            recovery_manager = get_recovery_manager()
            stats = recovery_manager.get_recovery_stats()

            return jsonify({
                "status": "ok",
                "recovery_stats": stats
            }), 200

        except Exception as e:
            logger.error(f"Failed to get recovery stats: {e}")
            return jsonify({
                "status": "error",
                "error": str(e)
            }), 500

    @app.route("/circuit_breakers", methods=["GET"])
    def circuit_breaker_status():
        """
        Get detailed circuit breaker status for all services.

        Returns:
            JSON with circuit breaker states
        """
        try:
            recovery_manager = get_recovery_manager()

            circuit_breakers = {
                name: cb.get_state()
                for name, cb in recovery_manager.circuit_breakers.items()
            }

            return jsonify({
                "status": "ok",
                "circuit_breakers": circuit_breakers
            }), 200

        except Exception as e:
            logger.error(f"Failed to get circuit breaker status: {e}")
            return jsonify({
                "status": "error",
                "error": str(e)
            }), 500

    @app.route("/reset_circuit_breaker/<service_name>", methods=["POST"])
    def reset_circuit_breaker(service_name: str):
        """
        Manually reset a circuit breaker (admin function).

        Args:
            service_name: Service name ('ollama', 'fastf1', 'modal')

        Returns:
            JSON with success status
        """
        try:
            recovery_manager = get_recovery_manager()

            if service_name not in recovery_manager.circuit_breakers:
                return jsonify({
                    "status": "error",
                    "error": f"Unknown service: {service_name}",
                    "available_services": list(recovery_manager.circuit_breakers.keys())
                }), 404

            recovery_manager.reset_circuit_breaker(service_name)

            logger.info(f"Circuit breaker reset for {service_name}")

            return jsonify({
                "status": "ok",
                "message": f"Circuit breaker reset for {service_name}"
            }), 200

        except Exception as e:
            logger.error(f"Failed to reset circuit breaker: {e}")
            return jsonify({
                "status": "error",
                "error": str(e)
            }), 500

    @app.route("/reset_all_circuit_breakers", methods=["POST"])
    def reset_all_circuit_breakers():
        """
        Reset all circuit breakers (admin function).

        Returns:
            JSON with success status
        """
        try:
            recovery_manager = get_recovery_manager()
            recovery_manager.reset_all_circuit_breakers()

            logger.info("All circuit breakers reset")

            return jsonify({
                "status": "ok",
                "message": "All circuit breakers reset"
            }), 200

        except Exception as e:
            logger.error(f"Failed to reset circuit breakers: {e}")
            return jsonify({
                "status": "error",
                "error": str(e)
            }), 500

    @app.route("/trigger_memory_cleanup", methods=["POST"])
    def trigger_memory_cleanup():
        """
        Manually trigger memory cleanup.

        Returns:
            JSON with cleanup results
        """
        try:
            recovery_manager = get_recovery_manager()
            result = recovery_manager.handle_memory_error(threshold_mb=0)  # Force cleanup

            if result:
                message = "Memory cleanup completed successfully"
            else:
                message = "No cleanup needed or cleanup failed"

            return jsonify({
                "status": "ok",
                "message": message,
                "cleanup_performed": result
            }), 200

        except Exception as e:
            logger.error(f"Failed to trigger memory cleanup: {e}")
            return jsonify({
                "status": "error",
                "error": str(e)
            }), 500
