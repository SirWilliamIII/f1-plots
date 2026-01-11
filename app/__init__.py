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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
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

# Custom function to get real client IP behind Cloudflare
def get_real_ip():
    """Get real client IP from X-Forwarded-For header (Cloudflare)"""
    # Cloudflare adds the real client IP to X-Forwarded-For
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        # First IP in the list is the real client
        return forwarded_for.split(',')[0].strip()
    # Fallback to direct connection (development)
    return request.remote_addr or '127.0.0.1'

# Initialize rate limiter (will be configured in create_app)
limiter = Limiter(
    key_func=get_real_ip,  # Use X-Forwarded-For for Cloudflare
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://",
    strategy="fixed-window"
)

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
    limiter.init_app(app)

    # Initialize FastF1 cache
    initialize_fastf1_cache("fastf1_cache")

    # Basic bot protection middleware
    @app.before_request
    def block_suspicious_requests():
        """Block obvious bot patterns"""
        # Skip static files and health checks
        if request.path.startswith('/static/') or request.path == '/health':
            return None

        user_agent = request.user_agent.string.lower() if request.user_agent and request.user_agent.string else ""

        # Block empty or suspicious user agents in production only
        suspicious_patterns = ['scraper']  # Only block obvious scrapers, allow curl/wget for testing
        if env == 'production' and any(pattern in user_agent for pattern in suspicious_patterns):
            logging.warning(f"Blocked suspicious user agent: {user_agent}")
            return jsonify({"error": "Forbidden"}), 403

        # Block requests without referrer to API endpoints (basic CSRF protection)
        # Only enforce in production
        if env == 'production' and request.path.startswith('/ollama_proxy/generate'):
            if not request.referrer or 'f1.linux-box.cc' not in request.referrer:
                logging.warning(f"Blocked request without valid referrer to {request.path}")
                return jsonify({"error": "Forbidden - Invalid request origin"}), 403

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

    # Rate limit error handler
    @app.errorhandler(429)
    def ratelimit_handler(e):
        """Custom handler for rate limit exceeded"""
        return jsonify({
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please slow down and try again later.",
            "retry_after": e.description
        }), 429

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
