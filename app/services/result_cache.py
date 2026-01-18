"""
Result Cache for F1 Telemetry Comparisons

Caches computed comparison results to disk for instant retrieval.
Historical F1 data never changes, so cached results are valid forever.
"""

import os
import pickle
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional, Tuple, Any
from threading import Lock
from io import BytesIO

# Cache directory
CACHE_DIR = Path("/home/will/f1-plots/comparison_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Thread safety
_cache_lock = Lock()

# Stats
_cache_stats = {
    'hits': 0,
    'misses': 0,
    'writes': 0
}


def get_cache_key(year: int, race: str, session_type: str, driver1: str, driver2: str) -> str:
    """Generate a unique cache key for a comparison."""
    # Sort drivers to ensure consistent keys regardless of order
    drivers = tuple(sorted([driver1.upper(), driver2.upper()]))
    key_str = f"{year}:{race}:{session_type}:{drivers[0]}:{drivers[1]}"
    return hashlib.md5(key_str.encode()).hexdigest()


def get_cache_path(cache_key: str) -> Path:
    """Get the file path for a cache key."""
    return CACHE_DIR / f"{cache_key}.pkl"


def get_cached_result(year: int, race: str, session_type: str,
                      driver1: str, driver2: str) -> Optional[Tuple]:
    """
    Retrieve a cached comparison result.

    Returns:
        The cached result tuple, or None if not cached.
    """
    cache_key = get_cache_key(year, race, session_type, driver1, driver2)
    cache_path = get_cache_path(cache_key)

    with _cache_lock:
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    result = pickle.load(f)

                # Reconstruct BytesIO from bytes
                if result and isinstance(result[0], bytes):
                    plot_bytes = result[0]
                    plot_buffer = BytesIO(plot_bytes)
                    result = (plot_buffer,) + result[1:]

                _cache_stats['hits'] += 1
                logging.info(f"📦 Cache HIT: {year} {race} {session_type} {driver1} vs {driver2}")
                return result
            except Exception as e:
                logging.warning(f"Cache read failed for {cache_key}: {e}")
                return None

        _cache_stats['misses'] += 1
        return None


def cache_result(year: int, race: str, session_type: str,
                 driver1: str, driver2: str, result: Tuple) -> bool:
    """
    Cache a comparison result.

    Args:
        year, race, session_type, driver1, driver2: Cache key components
        result: The comparison result tuple from compare_fastest_laps

    Returns:
        True if caching succeeded, False otherwise.
    """
    cache_key = get_cache_key(year, race, session_type, driver1, driver2)
    cache_path = get_cache_path(cache_key)

    try:
        # Convert BytesIO to bytes for serialization
        if result and hasattr(result[0], 'getvalue'):
            plot_buffer = result[0]
            plot_buffer.seek(0)
            plot_bytes = plot_buffer.getvalue()
            result_to_cache = (plot_bytes,) + result[1:]
        else:
            result_to_cache = result

        with _cache_lock:
            with open(cache_path, 'wb') as f:
                pickle.dump(result_to_cache, f)
            _cache_stats['writes'] += 1

        logging.info(f"💾 Cached: {year} {race} {session_type} {driver1} vs {driver2}")
        return True
    except Exception as e:
        logging.error(f"Cache write failed for {cache_key}: {e}")
        return False


def get_cache_stats() -> dict:
    """Get cache statistics."""
    cache_files = list(CACHE_DIR.glob("*.pkl"))
    total_size = sum(f.stat().st_size for f in cache_files)

    return {
        'hits': _cache_stats['hits'],
        'misses': _cache_stats['misses'],
        'writes': _cache_stats['writes'],
        'hit_rate': _cache_stats['hits'] / max(1, _cache_stats['hits'] + _cache_stats['misses']),
        'cached_comparisons': len(cache_files),
        'cache_size_mb': total_size / (1024 * 1024)
    }


def clear_cache() -> int:
    """Clear all cached results. Returns number of files deleted."""
    cache_files = list(CACHE_DIR.glob("*.pkl"))
    count = 0
    for f in cache_files:
        try:
            f.unlink()
            count += 1
        except Exception as e:
            logging.warning(f"Failed to delete {f}: {e}")

    logging.info(f"🗑️ Cleared {count} cached comparisons")
    return count


def list_cached_comparisons() -> list:
    """List all cached comparisons with metadata."""
    cache_files = list(CACHE_DIR.glob("*.pkl"))
    comparisons = []

    for f in cache_files:
        try:
            mtime = f.stat().st_mtime
            size = f.stat().st_size
            comparisons.append({
                'key': f.stem,
                'size_kb': size / 1024,
                'cached_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
            })
        except Exception:
            pass

    return sorted(comparisons, key=lambda x: x['cached_at'], reverse=True)
