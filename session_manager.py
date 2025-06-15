"""
Session Manager Module for F1 Telemetry Application

This module handles all FastF1 session caching, preloading, and optimization.
Separates session management concerns from the main Flask application.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from functools import lru_cache
import threading
import logging
import fastf1
from typing import Dict, List, Tuple, Optional


class SessionManager:
    """
    Manages FastF1 session caching and preloading for optimal performance.

    Like a pit crew chief coordinating tire changes - ensures sessions are
    ready when needed and handles the complex timing of data loading.
    """

    def __init__(self, max_workers: int = 2, enable_preloading: bool = True):
        self.cache: Dict[str, any] = {}
        self.cache_lock = threading.RLock()
        self.preload_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.enable_preloading = enable_preloading
        self._setup_logging()

        if enable_preloading:
            self.preload_popular_sessions()

    def _setup_logging(self):
        """Configure logging for session management"""
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def get_popular_sessions(self) -> List[Tuple[int, str, str]]:
        """
        Returns list of popular session combinations for preloading.

        These are the "greatest hits" - Monaco, Spa, Silverstone, etc.
        that users request most frequently.
        """
        return [
            # 2024 Popular Sessions
            (2024, "Monaco Grand Prix", "Q"),
            (2024, "Monaco Grand Prix", "R"),
            (2024, "Spanish Grand Prix", "Q"),
            (2024, "Spanish Grand Prix", "R"),
            (2024, "British Grand Prix", "Q"),
            (2024, "British Grand Prix", "R"),
            (2024, "Belgian Grand Prix", "Q"),
            (2024, "Belgian Grand Prix", "R"),
            # 2023 Popular Sessions (for comparison studies)
            (2023, "Monaco Grand Prix", "Q"),
            (2023, "Monaco Grand Prix", "R"),
            (2023, "Spanish Grand Prix", "Q"),
            (2023, "Spanish Grand Prix", "R"),
            (2023, "British Grand Prix", "Q"),
            (2023, "British Grand Prix", "R"),
            # 2022 Classic Sessions
            (2022, "Monaco Grand Prix", "Q"),
            (2022, "Monaco Grand Prix", "R"),
        ]

    def preload_popular_sessions(self):
        """
        Preload most commonly requested sessions in background threads.

        This is like warming up the engines before the race starts -
        ensures popular sessions are ready instantly when users request them.
        """
        popular_sessions = self.get_popular_sessions()

        self.logger.info(
            f"🔄 Starting preload of {len(popular_sessions)} popular sessions"
        )

        for year, race, session_type in popular_sessions:
            self.preload_executor.submit(
                self._preload_session, year, race, session_type
            )

    def _preload_session(self, year: int, race: str, session_type: str):
        """
        Background preloading of a single session.

        Args:
            year: F1 season year
            race: Race name (e.g., "Monaco Grand Prix")
            session_type: "Q" for qualifying, "R" for race
        """
        cache_key = self._generate_cache_key(year, race, session_type)

        try:
            with self.cache_lock:
                if cache_key in self.cache:
                    self.logger.debug(f"⏭️ Session already cached: {cache_key}")
                    return

            self.logger.info(f"🔄 Preloading session: {cache_key}")
            start_time = time.time()

            session = fastf1.get_session(year, race, session_type)
            session.load(
                telemetry=True,  # Essential for plotting
                weather=False,  # Skip for speed
                messages=False,  # Skip for speed
            )

            load_time = time.time() - start_time

            with self.cache_lock:
                self.cache[cache_key] = session

            self.logger.info(f"✅ Preloaded session in {load_time:.2f}s: {cache_key}")

        except Exception as e:
            self.logger.warning(f"⚠️ Failed to preload {cache_key}: {str(e)}")

    def _generate_cache_key(self, year: int, race: str, session_type: str) -> str:
        """Generate consistent cache key for session identification"""
        return f"{year}_{race}_{session_type}"

    def get_session(self, year: int, race: str, session_type: str):
        """
        Get session with improved caching and error handling.

        This is the main entry point - like the race director coordinating
        everything to ensure drivers get what they need when they need it.

        Args:
            year: F1 season year
            race: Race name
            session_type: "Q" for qualifying, "R" for race

        Returns:
            FastF1 session object with telemetry data loaded

        Raises:
            Exception: If session cannot be loaded after timeout
        """
        cache_key = self._generate_cache_key(year, race, session_type)

        # Check cache first (with lock for thread safety)
        with self.cache_lock:
            if cache_key in self.cache:
                self.logger.info(f"🚀 Using cached session: {cache_key}")
                return self.cache[cache_key]

        # Load session with timeout protection
        return self._load_session_with_timeout(year, race, session_type, cache_key)

    def _load_session_with_timeout(
        self, year: int, race: str, session_type: str, cache_key: str
    ):
        """
        Load session with comprehensive error handling and timeout protection.

        Like having a backup plan when the primary strategy fails - ensures
        the system remains responsive even when FastF1 API is slow.
        """
        start_time = time.time()
        max_load_time = 120  # 2 minute timeout

        try:
            self.logger.info(f"🔄 Loading new session: {cache_key}")

            session = fastf1.get_session(year, race, session_type)

            # Load with optimized settings for plotting
            session.load(
                telemetry=True,  # Required for telemetry comparison
                weather=False,  # Skip weather data for speed
                messages=False,  # Skip race control messages
                laps=True,  # Need lap data for fastest lap selection
            )

            load_time = time.time() - start_time

            if load_time > max_load_time:
                raise TimeoutError(f"Session loading exceeded {max_load_time}s limit")

            # Cache the successfully loaded session
            with self.cache_lock:
                self.cache[cache_key] = session

            self.logger.info(f"✅ Loaded new session in {load_time:.2f}s: {cache_key}")
            return session

        except Exception as e:
            load_time = time.time() - start_time
            error_msg = (
                f"Failed to load session after {load_time:.2f}s: {cache_key} - {str(e)}"
            )
            self.logger.error(f"❌ {error_msg}")

            # Provide helpful error context
            if "SessionNotAvailableError" in str(e):
                raise Exception(
                    f"Session data not available for {year} {race} {session_type}. "
                    f"Try a different year/race combination."
                )
            elif load_time > max_load_time:
                raise Exception(
                    f"Session loading timed out after {max_load_time}s. "
                    f"Please try again or select a different session."
                )
            else:
                raise Exception(f"Failed to load session data: {str(e)}")

    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get cache statistics for monitoring and debugging.

        Returns:
            Dictionary with cache size, hit rate, and other metrics
        """
        with self.cache_lock:
            return {
                "cached_sessions": len(self.cache),
                "cache_keys": list(self.cache.keys()),
                "memory_usage_mb": sum(
                    getattr(session, "_memory_usage", 0)
                    for session in self.cache.values()
                )
                / (1024 * 1024),
            }

    def clear_cache(self, keep_popular: bool = True):
        """
        Clear session cache, optionally keeping popular sessions.

        Args:
            keep_popular: If True, keeps preloaded popular sessions
        """
        with self.cache_lock:
            if keep_popular:
                popular_keys = {
                    self._generate_cache_key(year, race, session_type)
                    for year, race, session_type in self.get_popular_sessions()
                }

                keys_to_remove = [
                    key for key in self.cache.keys() if key not in popular_keys
                ]

                for key in keys_to_remove:
                    del self.cache[key]

                self.logger.info(
                    f"🧹 Cleared {len(keys_to_remove)} non-popular sessions from cache"
                )
            else:
                cache_size = len(self.cache)
                self.cache.clear()
                self.logger.info(f"🧹 Cleared all {cache_size} sessions from cache")

    def shutdown(self):
        """Gracefully shutdown the session manager and thread pool"""
        self.logger.info("🛑 Shutting down session manager...")
        self.preload_executor.shutdown(wait=True)
        self.clear_cache(keep_popular=False)


# Cache for race schedules (they don't change often)
@lru_cache(maxsize=10)
def get_races_cached(year: int) -> List[Dict[str, str]]:
    """
    Cache race schedules since they don't change during the season.

    Like keeping a season calendar handy - no need to re-fetch
    the same race schedule multiple times.

    Args:
        year: F1 season year

    Returns:
        List of race dictionaries with country and event_name

    Raises:
        Exception: If race schedule cannot be fetched
    """
    try:
        df = fastf1.get_event_schedule(year, include_testing=False)
        races = [
            {"country": row["Country"], "event_name": row["EventName"]}
            for _, row in df.iterrows()
        ]

        logging.info(f"📅 Cached {len(races)} races for {year}")
        return races

    except Exception as e:
        logging.error(f"❌ Failed to fetch races for {year}: {str(e)}")
        raise Exception(f"Failed to fetch race schedule for {year}: {str(e)}")


def initialize_fastf1_cache(cache_dir: str = "fastf1_cache"):
    """
    Initialize FastF1 cache directory and plotting setup.

    Args:
        cache_dir: Directory path for FastF1 cache
    """
    import os
    from fastf1 import plotting

    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)

    # Setup plotting with F1 color scheme
    plotting.setup_mpl(color_scheme="fastf1", misc_mpl_mods=False)

    logging.info(f"🎨 FastF1 cache and plotting initialized: {cache_dir}")


# Global session manager instance (initialized in app.py)
session_manager: Optional[SessionManager] = None
