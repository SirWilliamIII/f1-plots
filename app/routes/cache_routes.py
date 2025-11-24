"""
Cache Management Routes

Handles cache statistics, clearing, and GPU warmup.
"""

import os
import gc
import logging
import threading
import requests
from datetime import datetime
from flask import jsonify
from app.middleware.cleanup import get_session_manager
from app.services.context_service import cleanup_old_contexts


def register_cache_routes(app):
    """Register cache management routes"""

    @app.route("/cache_stats")
    def cache_stats():
        """Debug endpoint to view session cache statistics"""
        session_manager = get_session_manager()
        if session_manager:
            stats = session_manager.get_cache_stats()
            return {"cache_stats": stats, "message": "Session manager is running"}
        return {"error": "Session manager not initialized"}, 500

    @app.route("/clear_cache", methods=["POST"])
    def clear_cache():
        """Administrative endpoint to clear session cache"""
        session_manager = get_session_manager()
        if session_manager:
            session_manager.clear_cache(keep_popular=True)
            return {"message": "Cache cleared successfully"}
        return {"error": "Session manager not available"}, 500

    @app.route("/optimize_cache", methods=["POST"])
    def optimize_cache():
        """Trigger cache optimization"""
        try:
            # Force cleanup of expired contexts
            cleanup_old_contexts()

            # Clear old session cache entries
            session_manager = get_session_manager()
            session_manager.clear_cache(keep_popular=True)

            # Force garbage collection
            gc.collect()

            return jsonify({
                'message': 'Cache optimization completed',
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route("/warmup_gpu", methods=["POST"])
    def warmup_gpu():
        """
        Warmup endpoint - triggers GPU container to wake up.
        Called when user visits the site to eliminate cold starts.
        """
        def warmup_background():
            try:
                import time
                start = time.time()
                ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

                # If using Modal proxy, forward to its warmup endpoint
                if "11435" in ollama_url:  # Port 11435 = Modal proxy
                    logging.info("🔥 Warming up Modal GPU (background)...")
                    response = requests.post(f"{ollama_url}/warmup", timeout=60)
                    elapsed = time.time() - start
                    logging.info(f"✓ GPU warmed in {elapsed:.1f}s")
                else:
                    # Local Ollama - just ping it
                    logging.info("🔥 Warming up local Ollama...")
                    requests.post(
                        f"{ollama_url}/api/generate",
                        json={"model": "qwen2.5-coder:7b", "prompt": "Ready", "stream": False},
                        timeout=30
                    )
                    elapsed = time.time() - start
                    logging.info(f"✓ Local Ollama warmed in {elapsed:.1f}s")
            except Exception as e:
                logging.warning(f"⚠ GPU warmup failed: {e}")

        # Start warmup in background thread - don't block page load!
        thread = threading.Thread(target=warmup_background, daemon=True)
        thread.start()

        # Return immediately
        return {"status": "warming", "message": "GPU warmup started in background"}, 200
