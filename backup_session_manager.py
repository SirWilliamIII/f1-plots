"""
Session Manager for F1 Telemetry Application

Manages FastF1 session loading with caching and performance optimization.
"""

import fastf1
import logging
import os
from threading import Lock, Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple, List, Optional
import time
from functools import lru_cache


def initialize_fastf1_cache(cache_dir: str = "fastf1_cache"):
    """Initialize FastF1 cache directory"""
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    fastf1.Cache.enable_cache(cache_dir)
    logging.info(f"FastF1 cache enabled at: {cache_dir}")


@lru_cache(maxsize=50)
def get_races_cached(year: int) -> List:
    """Get races for a given year with caching"""
    try:
        schedule = fastf1.get_event_schedule(year)
        return schedule['EventName'].tolist()
    except Exception as e:
        logging.error(f"Failed to get races for year {year}: {e}")
        return []


class SessionManager:
    """
    Thread-safe session manager with caching and preloading capabilities.
    """
    
    def __init__(self, max_workers: int = 2, enable_preloading: bool = True, max_cache_size: int = 50):
        self.max_workers = max_workers
        self.enable_preloading = enable_preloading
        self.max_cache_size = max_cache_size
        
        # Cache storage
        self._session_cache: Dict[Tuple[int, str, str], object] = {}
        self._cache_lock = Lock()
        
        # Thread pool for background operations
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._preload_count = 0
        
        logging.info(f"SessionManager initialized with {max_workers} workers, preloading={'enabled' if enable_preloading else 'disabled'}")
        
        # Start preloading popular sessions if enabled
        if enable_preloading:
            self._start_preloading()
    
    def _start_preloading(self):
        """Start preloading popular sessions in background"""
        popular_sessions = [
            (2024, "Monaco Grand Prix", "Q"),
            (2024, "Monaco Grand Prix", "R"),
            (2024, "British Grand Prix", "Q"),
            (2023, "Monaco Grand Prix", "Q"),
            (2023, "British Grand Prix", "Q"),
        ]
        
        def preload_worker():
            for year, race, session_type in popular_sessions:
                try:
                    self._load_session_internal(year, race, session_type, is_preload=True)
                    self._preload_count += 1
                    logging.info(f"Preloaded: {year} {race} {session_type}")
                except Exception as e:
                    logging.warning(f"Failed to preload {year} {race} {session_type}: {e}")
        
        # Submit preloading task
        self._executor.submit(preload_worker)
    
    def get_session(self, year: int, race: str, session_type: str):
        """
        Get a session, using cache if available or loading if not.
        
        Args:
            year: Race year
            race: Race name
            session_type: 'Q' for Qualifying, 'R' for Race
        
        Returns:
            FastF1 session object
        """
        cache_key = (year, race, session_type)
        
        # Check cache first
        with self._cache_lock:
            if cache_key in self._session_cache:
                self._cache_hits += 1
                logging.info(f"Cache hit: {year} {race} {session_type}")
                return self._session_cache[cache_key]
        
        # Not in cache, load it
        self._cache_misses += 1
        logging.info(f"Cache miss: {year} {race} {session_type}")
        return self._load_session_internal(year, race, session_type)
    
    def _load_session_internal(self, year: int, race: str, session_type: str, is_preload: bool = False):
        """Internal method to load a session"""
        cache_key = (year, race, session_type)
        
        try:
            # Load the session
            session = fastf1.get_session(year, race, session_type)
            session.load()
            
            # Add to cache
            with self._cache_lock:
                # Implement simple LRU by removing oldest if cache is full
                if len(self._session_cache) >= self.max_cache_size:
                    # Remove first (oldest) item
                    oldest_key = next(iter(self._session_cache))
                    del self._session_cache[oldest_key]
                    logging.info(f"Evicted from cache: {oldest_key}")
                
                self._session_cache[cache_key] = session
            
            action = "preloaded" if is_preload else "loaded"
            logging.info(f"Successfully {action}: {year} {race} {session_type}")
            return session
            
        except Exception as e:
            logging.error(f"Failed to load session {year} {race} {session_type}: {e}")
            raise
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        with self._cache_lock:
            return {
                "cache_size": len(self._session_cache),
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0,
                "preloaded_sessions": self._preload_count,
                "cached_sessions": list(self._session_cache.keys())
            }
    
    def clear_cache(self, keep_popular: bool = False):
        """Clear the session cache"""
        with self._cache_lock:
            if keep_popular:
                # Keep popular sessions
                popular_keys = [
                    (2024, "Monaco Grand Prix", "Q"),
                    (2024, "Monaco Grand Prix", "R"),
                    (2024, "British Grand Prix", "Q"),
                ]
                new_cache = {k: v for k, v in self._session_cache.items() if k in popular_keys}
                self._session_cache = new_cache
                logging.info(f"Cache cleared, kept {len(new_cache)} popular sessions")
            else:
                self._session_cache.clear()
                logging.info("Cache completely cleared")
    
    def preload_session(self, year: int, race: str, session_type: str):
        """Manually trigger preloading of a specific session"""
        cache_key = (year, race, session_type)
        
        with self._cache_lock:
            if cache_key in self._session_cache:
                logging.info(f"Session already cached: {year} {race} {session_type}")
                return
        
        # Submit to thread pool
        future = self._executor.submit(self._load_session_internal, year, race, session_type, True)
        logging.info(f"Queued for preload: {year} {race} {session_type}")
        return future
    
    def shutdown(self):
        """Shutdown the session manager"""
        self._executor.shutdown(wait=True)
        logging.info("SessionManager shutdown complete")