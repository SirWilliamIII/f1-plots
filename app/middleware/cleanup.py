"""
Request Cleanup Middleware

Handles memory cleanup and warmup hooks.
"""

import gc
import logging
from session_manager import SessionManager

# Global session manager
session_manager = None


def init_session_manager():
    """Initialize the global session manager"""
    global session_manager
    session_manager = SessionManager(
        max_workers=2,  # 2 background threads for preloading
        enable_preloading=False,  # Disable preloading by default
        max_cache_size=5,  # Reduced from default 50 to 5 to save memory
    )
    return session_manager


def register_cleanup_hooks(app):
    """Register memory cleanup and warmup hooks"""
    import os
    global session_manager
    session_manager = init_session_manager()

    @app.after_request
    def after_request_cleanup(response):
        """Clean up memory and record metrics after each request"""
        from config import FLASK_CONFIG
        from app.services.memory_service import check_memory_usage
        from flask import request
        from app.metrics import REQUEST_COUNT

        # ✅ FIXED: Record metrics based on ACTUAL response status
        # This prevents double-counting (success + error)
        if request.endpoint:
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.endpoint,
                status=response.status_code
            ).inc()

        if FLASK_CONFIG.enable_gc_after_request:
            # Always do light cleanup
            gc.collect()

            # Check if we need aggressive cleanup
            check_memory_usage()

        return response

    # ✅ FIXED: Run cache warmup ONCE in background, not on every request
    if not os.getenv("MODAL_DEPLOYMENT", "").lower() == "true":
        if not hasattr(app, '_cache_warmed'):
            app._cache_warmed = True
            _warm_cache_background(session_manager)


def _warm_cache_background(session_manager):
    """
    Warm cache in background thread (runs once on startup)

    ✅ FIXED: Previously ran on EVERY request, blocking all users.
              Now runs once in background thread.
    """
    import threading
    from config import SESSION_CONFIG

    # Skip if preloading disabled
    if not SESSION_CONFIG.enable_preloading:
        logging.info("⏭️  Cache preloading disabled in config")
        return

    def warmup_worker():
        """Background thread worker"""
        try:
            logging.info("🔥 Starting cache warmup (background, non-blocking)")

            popular_sessions = [
                (2024, "British Grand Prix", "R"),
                (2024, "Monaco Grand Prix", "Q"),
                (2023, "Abu Dhabi Grand Prix", "R"),
            ]

            for year, race, session_type in popular_sessions:
                try:
                    session_manager.preload_session(year, race, session_type)
                    logging.info(f"✅ Preloaded: {year} {race} {session_type}")
                except Exception as e:
                    logging.warning(f"⚠️  Failed to preload {year} {race}: {e}")

            logging.info("🎉 Cache warmup complete")
        except Exception as e:
            logging.error(f"💥 Cache warmup failed: {e}")

    # Start warmup in background thread (daemon = exits when app exits)
    warmup_thread = threading.Thread(target=warmup_worker, daemon=True)
    warmup_thread.start()
    logging.info("🚀 Cache warmup started in background (non-blocking)")


def get_session_manager():
    """Get the global session manager instance"""
    global session_manager
    if session_manager is None:
        session_manager = init_session_manager()
    return session_manager
