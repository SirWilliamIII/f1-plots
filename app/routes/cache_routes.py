"""
Cache Management Routes

Handles cache statistics, clearing, and GPU warmup.
"""

import os
import gc
import logging
import threading
import requests
import time
from datetime import datetime
from flask import jsonify
from app.middleware.cleanup import get_session_manager
from app.services.context_service import cleanup_old_contexts
from app.services.result_cache import get_cache_stats as get_result_cache_stats, list_cached_comparisons

# Global warmup state - Beam container stays warm for 10 min, so we only need to warm every 8 min
_last_warmup_time = 0
_warmup_cooldown_seconds = 480  # 8 minutes
_warmup_lock = threading.Lock()


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

        Uses global cooldown to prevent duplicate warmups - Beam container
        stays warm for 10 minutes, so we only trigger warmup every 8 minutes.
        """
        global _last_warmup_time

        current_time = time.time()
        time_since_last = current_time - _last_warmup_time

        # Check if we're still in cooldown period
        if time_since_last < _warmup_cooldown_seconds:
            remaining = int(_warmup_cooldown_seconds - time_since_last)
            logging.info(f"⏳ GPU warmup skipped - container still warm ({remaining}s remaining)")
            return {
                "status": "already_warm",
                "message": f"GPU container still warm, next warmup in {remaining}s"
            }, 200

        # Try to acquire lock to prevent concurrent warmups
        if not _warmup_lock.acquire(blocking=False):
            logging.info("⏳ GPU warmup already in progress")
            return {"status": "in_progress", "message": "Warmup already running"}, 200

        try:
            # Update timestamp before starting warmup
            _last_warmup_time = current_time

            def warmup_background():
                try:
                    start = time.time()
                    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

                    # If using Beam proxy, forward to its warmup endpoint
                    if "11435" in ollama_url:  # Port 11435 = Beam proxy
                        logging.info("🔥 Warming up Beam GPU (background)...")
                        response = requests.post(f"{ollama_url}/warmup", timeout=120)
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
                finally:
                    _warmup_lock.release()

            # Start warmup in background thread - don't block page load!
            thread = threading.Thread(target=warmup_background, daemon=True)
            thread.start()

            # Return immediately
            return {"status": "warming", "message": "GPU warmup started in background"}, 200

        except Exception as e:
            _warmup_lock.release()
            logging.error(f"Warmup error: {e}")
            return {"status": "error", "message": str(e)}, 500

    @app.route("/cache/results")
    def result_cache_stats():
        """Get statistics for the comparison result cache."""
        try:
            stats = get_result_cache_stats()
            return jsonify({
                'status': 'ok',
                'cache': stats
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route("/cache/results/list")
    def list_result_cache():
        """List all cached comparison results."""
        try:
            comparisons = list_cached_comparisons()
            stats = get_result_cache_stats()
            return jsonify({
                'status': 'ok',
                'total': len(comparisons),
                'size_mb': stats['cache_size_mb'],
                'comparisons': comparisons[:50]  # Limit to 50 most recent
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
