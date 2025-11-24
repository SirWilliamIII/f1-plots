"""
F1 Telemetry Application Entry Point

This is the main entry point for the Flask application using the refactored
modular structure.

Usage:
    python run.py
    # Or with uv:
    uv run python run.py
"""

import os
import logging
from app import create_app

# Initialize the app using factory pattern
app = create_app()

# Initialize performance optimizations
if not hasattr(app, "_initialized"):
    app._initialized = True
    logging.info("✅ Application initialized successfully")

    # Warm up matplotlib to reduce first-plot latency
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 1, figsize=(1, 1))
    plt.close(fig)

    logging.info("🚀 Backend optimizations initialized")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5151))
    logging.info(f"🚀 Starting Flask app on port: {port}")
    logging.info(f"🌐 Access the app at: http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)
