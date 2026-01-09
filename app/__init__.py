"""
F1 Telemetry Application - Modular Flask App

This package contains the refactored Flask application split into:
- routes: API endpoints organized by functionality
- services: Business logic and data processing
- plotting: Telemetry visualization and plot generation
- middleware: Request/response handling
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import logging
from flask import Flask, jsonify, request
from flask_compress import Compress
from flask_cors import CORS
from dotenv import load_dotenv
from session_manager import initialize_fastf1_cache
from app.error_tracking.error_tracker import get_error_tracker, ErrorSeverity

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Initialize global error tracker
error_tracker = get_error_tracker({
    'max_queue_size': 1000,
    'rate_limit_window': 60,
    'max_errors_per_window': 10
})

logging.info("🔥 F1 App Performance Upgrades Loaded:")
logging.info("  ✅ Smart Session Manager with analytics")
logging.info("  ✅ Track-aware interpolation system")
logging.info("  ✅ Memory-optimized matplotlib handling")
logging.info("  ✅ Request-scoped context management")
logging.info("  ✅ Concurrent user support enabled")

# Load environment
env = os.getenv('FLASK_ENV', 'development')
if env == 'production':
    load_dotenv('.env.prod')
else:
    load_dotenv('.env')

# Configure matplotlib
os.environ["MPLBACKEND"] = "Agg"
os.environ["MPLCONFIGDIR"] = "/tmp"
plt.switch_backend("Agg")

def create_app():
    """Application factory pattern"""
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    # Configuration
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'f1-telemetry-secret-key-change-in-production')

    # Extensions
    Compress(app)
    CORS(app)

    # Initialize FastF1 cache
    initialize_fastf1_cache("fastf1_cache")

    # Register middleware
    from app.middleware.cleanup import register_cleanup_hooks
    from app.middleware.error_middleware import register_error_middleware
    register_cleanup_hooks(app)
    register_error_middleware(app)

    # Register routes
    from app.routes.ollama_routes import register_ollama_routes
    from app.routes.api_routes import register_api_routes
    from app.routes.cache_routes import register_cache_routes
    from app.routes.main_routes import register_main_routes
    from app.routes.plot_routes import register_plot_routes
    from app.routes.memory_routes import register_memory_routes
    from app.routes.error_dashboard_routes import register_error_dashboard_routes
    from app.routes.recovery_routes import register_recovery_routes

    register_ollama_routes(app)
    register_api_routes(app)
    register_cache_routes(app)
    register_main_routes(app)
    register_plot_routes(app)
    register_memory_routes(app)
    register_error_dashboard_routes(app)
    register_recovery_routes(app)

    # Error handlers with ErrorTracker integration
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Handle HTTP exceptions (4xx, 5xx)"""
        # Only track 5xx errors as they indicate server issues
        if e.code >= 500:
            context = {
                'url': request.url,
                'method': request.method,
                'endpoint': request.endpoint,
                'user_agent': request.user_agent.string,
                'remote_addr': request.remote_addr
            }
            error_tracker.capture_message(
                f"HTTP {e.code}: {e.description}",
                level=ErrorSeverity.ERROR,
                context=context
            )
        return e

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all uncaught exceptions"""
        # Skip HTTP exceptions (already handled above)
        if isinstance(e, HTTPException):
            return handle_http_exception(e)

        # Capture exception with context
        context = {
            'url': request.url,
            'method': request.method,
            'endpoint': request.endpoint,
            'user_agent': request.user_agent.string,
            'remote_addr': request.remote_addr,
            'form_data': dict(request.form) if request.form else None,
            'json_data': request.get_json(silent=True)
        }

        fingerprint = error_tracker.capture_exception(
            e,
            context=context,
            level=ErrorSeverity.ERROR
        )

        logging.error(f"Unhandled exception (fingerprint: {fingerprint}): {str(e)}", exc_info=True)

        from flask import render_template
        return render_template("error.html", error_message=str(e)), 500

    # Test endpoint for error tracking (development only)
    if env == 'development':
        @app.route('/test/trigger_error')
        def trigger_test_error():
            """Deliberately trigger an error to test error tracking"""
            raise ValueError("This is a test error to verify error tracking is working!")

    return app
