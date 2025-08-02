"""
Configuration settings for F1 Telemetry Application

Centralizes all configuration in one place for easy tuning.
"""

import os
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class SessionManagerConfig:
    """Configuration for the SessionManager class"""

    # Threading configuration
    max_workers: int = 2
    enable_preloading: bool = True

    # Cache configuration  
    max_cache_size: int = 10  # Maximum number of sessions to cache (reduced for memory)
    cache_directory: str = "fastf1_cache"

    # Performance tuning
    session_timeout: int = 180  # seconds
    preload_timeout: int = 300  # seconds

    # Popular sessions for preloading (can be customized based on analytics)
    popular_sessions: List[Tuple[int, str, str]] = None

    def __post_init__(self):
        """Set default popular sessions if not provided"""
        if self.popular_sessions is None:
            self.popular_sessions = [
                # Only preload the most popular sessions to save memory
                (2024, "Monaco Grand Prix", "Q"),
                (2024, "British Grand Prix", "Q"),
                (2023, "Monaco Grand Prix", "Q"),
            ]


@dataclass
class FlaskConfig:
    """Flask application configuration"""

    # Server configuration
    host: str = "0.0.0.0"
    port: int = int(os.getenv("PORT", 8080))
    debug: bool = os.getenv("FLASK_ENV") == "development"

    # Request handling
    max_content_length: int = 16 * 1024 * 1024  # 16MB
    request_timeout: int = 300  # 5 minutes

    # Memory management
    enable_gc_after_request: bool = True  # Force garbage collection after requests
    memory_threshold_mb: int = 300  # Trigger cleanup when app uses more than this
    matplotlib_cleanup: bool = True  # Clear matplotlib figures after use

    # Logging
    log_level: str = "INFO"


@dataclass
class GunicornConfig:
    """Gunicorn configuration for production deployment"""

    workers: int = 1
    threads: int = 8
    worker_class: str = "gthread"
    timeout: int = 300
    keepalive: int = 5
    max_requests: int = 1000
    max_requests_jitter: int = 100
    preload_app: bool = True
    worker_tmp_dir: str = "/dev/shm"


# Create default configurations
SESSION_CONFIG = SessionManagerConfig()
FLASK_CONFIG = FlaskConfig()
GUNICORN_CONFIG = GunicornConfig()

# Environment-specific overrides
if os.getenv("FLASK_ENV") == "development":
    SESSION_CONFIG.max_workers = 1
    SESSION_CONFIG.enable_preloading = False
    FLASK_CONFIG.debug = True

elif os.getenv("FLASK_ENV") == "production":
    SESSION_CONFIG.max_workers = 2
    SESSION_CONFIG.enable_preloading = True
    FLASK_CONFIG.debug = False
