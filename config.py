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
    enable_preloading: bool = False  # Disabled to prevent cache thrashing

    # Cache configuration
    max_cache_size: int = 20  # Maximum number of sessions to cache
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


@dataclass
class ModalConfig:
    """Modal deployment configuration"""

    # Deployment mode
    enabled: bool = os.getenv("MODAL_DEPLOYMENT", "false").lower() == "true"

    # GPU configuration
    gpu_type: str = "T4"  # Options: T4, A10, L4, A100
    gpu_timeout: int = 120  # seconds
    gpu_idle_timeout: int = 300  # Keep warm for 5 minutes

    # Volume configuration
    volume_name: str = "f1-data"
    cache_path: str = "/cache/fastf1_cache"  # Path within Modal volume

    # Ollama configuration
    ollama_model: str = "qwen2.5-coder:7b"  # Use base model (f1-analyst crashes on Modal)
    ollama_temperature: float = 0.1

    # Flask app configuration
    flask_memory_mb: int = 8192  # 8GB RAM
    flask_timeout: int = 300  # 5 minutes
    flask_idle_timeout: int = 600  # Keep warm for 10 minutes
    keep_warm_instances: int = 0  # 0 = scale to zero, 1+ = keep N instances warm

    # Cache warming schedule (cron format)
    cache_warming_schedule: str = "0 0 * * *"  # Daily at midnight


# Create default configurations
SESSION_CONFIG = SessionManagerConfig()
FLASK_CONFIG = FlaskConfig()
GUNICORN_CONFIG = GunicornConfig()
MODAL_CONFIG = ModalConfig()

# Environment-specific overrides
import logging
logging.info(f"🔧 FLASK_ENV={os.getenv('FLASK_ENV')}")
if os.getenv("FLASK_ENV") == "development":
    SESSION_CONFIG.max_workers = 1
    SESSION_CONFIG.enable_preloading = False
    FLASK_CONFIG.debug = True

elif os.getenv("FLASK_ENV") == "production":
    SESSION_CONFIG.max_workers = 2
    SESSION_CONFIG.enable_preloading = True
    FLASK_CONFIG.debug = False

# Modal deployment overrides
if MODAL_CONFIG.enabled:
    # Use Modal volume paths
    SESSION_CONFIG.cache_directory = MODAL_CONFIG.cache_path
    # Disable local preloading (use Modal's cache warming instead)
    SESSION_CONFIG.enable_preloading = False
    # Reduce workers (Modal handles concurrency)
    SESSION_CONFIG.max_workers = 1
