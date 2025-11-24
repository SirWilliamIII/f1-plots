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
from flask import Flask
from flask_compress import Compress
from flask_cors import CORS
from dotenv import load_dotenv
from session_manager import initialize_fastf1_cache

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
    register_cleanup_hooks(app)

    # Register routes
    from app.routes.ollama_routes import register_ollama_routes
    from app.routes.api_routes import register_api_routes
    from app.routes.cache_routes import register_cache_routes
    from app.routes.main_routes import register_main_routes
    from app.routes.plot_routes import register_plot_routes
    from app.routes.memory_routes import register_memory_routes

    register_ollama_routes(app)
    register_api_routes(app)
    register_cache_routes(app)
    register_main_routes(app)
    register_plot_routes(app)
    register_memory_routes(app)

    # Error handlers
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e
        from flask import render_template
        return render_template("error.html", error_message=str(e)), 500

    return app
