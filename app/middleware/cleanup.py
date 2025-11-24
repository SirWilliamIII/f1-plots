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
    global session_manager
    session_manager = init_session_manager()

    @app.after_request
    def after_request_cleanup(response):
        """Clean up memory after each request"""
        from config import FLASK_CONFIG
        from app.services.memory_service import check_memory_usage

        if FLASK_CONFIG.enable_gc_after_request:
            # Always do light cleanup
            gc.collect()

            # Check if we need aggressive cleanup
            check_memory_usage()

        return response

    @app.before_request
    def warm_cache():
        """Pre-load popular sessions into cache"""
        popular_sessions = [
            (2024, "British Grand Prix", "R"),
            (2024, "Monaco Grand Prix", "Q"),
            (2023, "Abu Dhabi Grand Prix", "R"),
        ]

        for year, race, session_type in popular_sessions:
            try:
                session_manager.get_session(year, race, session_type)
                logging.info(f"✅ Pre-loaded {year} {race} {session_type}")
            except Exception as e:
                logging.warning(f"Could not pre-load {year} {race}: {e}")


def get_session_manager():
    """Get the global session manager instance"""
    global session_manager
    if session_manager is None:
        session_manager = init_session_manager()
    return session_manager
