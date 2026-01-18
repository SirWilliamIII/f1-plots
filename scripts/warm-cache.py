#!/usr/bin/env python3
"""
Cache Pre-Warming Script for F1 Telemetry App

Populates the comparison cache with popular driver combinations.
Run this to pre-compute results for instant page loads.

Usage:
    uv run scripts/warm-cache.py                    # Warm 2024-2025 races
    uv run scripts/warm-cache.py --year 2023        # Warm specific year
    uv run scripts/warm-cache.py --all              # Warm all years (2020-2025)
    uv run scripts/warm-cache.py --top-drivers      # Only top 6 drivers per race
    uv run scripts/warm-cache.py --dry-run          # Show what would be cached
"""

import sys
import os
import argparse
import logging
import time
from itertools import combinations
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up matplotlib before importing app modules
import matplotlib
matplotlib.use('Agg')

import fastf1
from session_manager import initialize_fastf1_cache, get_races_cached
from app.plotting.telemetry_plots import compare_fastest_laps
from app.services.result_cache import (
    get_cached_result, cache_result, get_cache_stats,
    get_cache_key, get_cache_path
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# Top drivers by season (most likely to be compared)
TOP_DRIVERS = {
    2024: ['VER', 'NOR', 'LEC', 'SAI', 'HAM', 'RUS', 'PIA', 'ALO'],
    2023: ['VER', 'PER', 'HAM', 'RUS', 'LEC', 'SAI', 'NOR', 'ALO'],
    2022: ['VER', 'LEC', 'PER', 'RUS', 'SAI', 'HAM', 'NOR', 'ALO'],
    2021: ['VER', 'HAM', 'BOT', 'PER', 'NOR', 'LEC', 'SAI', 'RIC'],
    2020: ['HAM', 'BOT', 'VER', 'PER', 'LEC', 'SAI', 'NOR', 'RIC'],
}


def get_session_drivers(year: int, race: str, session_type: str) -> list:
    """Get list of drivers who participated in a session."""
    try:
        session = fastf1.get_session(year, race, session_type)
        session.load(telemetry=False, weather=False, messages=False)
        return list(session.drivers)
    except Exception as e:
        logging.warning(f"Failed to get drivers for {year} {race}: {e}")
        return []


def get_driver_abbreviations(session) -> list:
    """Get driver abbreviations from a session."""
    try:
        return [session.get_driver(num)['Abbreviation'] for num in session.drivers]
    except Exception:
        return []


def warm_comparison(year: int, race: str, session_type: str,
                    driver1: str, driver2: str, dry_run: bool = False) -> bool:
    """Warm a single comparison into the cache."""
    # Check if already cached
    if get_cached_result(year, race, session_type, driver1, driver2):
        logging.info(f"  [SKIP] Already cached: {driver1} vs {driver2}")
        return True

    if dry_run:
        logging.info(f"  [DRY] Would cache: {driver1} vs {driver2}")
        return True

    try:
        # Load session
        session = fastf1.get_session(year, race, session_type)
        session.load()

        # Generate comparison
        start = time.time()
        result = compare_fastest_laps(session, driver1, driver2)
        elapsed = time.time() - start

        # Cache result
        cache_result(year, race, session_type, driver1, driver2, result)
        logging.info(f"  [OK] Cached {driver1} vs {driver2} ({elapsed:.1f}s)")
        return True

    except Exception as e:
        logging.error(f"  [ERR] Failed {driver1} vs {driver2}: {e}")
        return False


def warm_race(year: int, race: str, session_type: str = 'Q',
              top_drivers_only: bool = False, dry_run: bool = False) -> dict:
    """Warm all driver combinations for a race."""
    logging.info(f"\n{'='*60}")
    logging.info(f"Warming: {year} {race} ({session_type})")
    logging.info(f"{'='*60}")

    stats = {'cached': 0, 'skipped': 0, 'failed': 0}

    try:
        # Load session to get drivers
        session = fastf1.get_session(year, race, session_type)
        session.load(telemetry=False, weather=False, messages=False)

        drivers = [session.get_driver(num)['Abbreviation'] for num in session.drivers]
        logging.info(f"Found {len(drivers)} drivers")

        # Filter to top drivers if requested
        if top_drivers_only and year in TOP_DRIVERS:
            drivers = [d for d in drivers if d in TOP_DRIVERS[year]]
            logging.info(f"Filtered to {len(drivers)} top drivers")

        # Generate all combinations
        driver_pairs = list(combinations(drivers, 2))
        logging.info(f"Processing {len(driver_pairs)} combinations...")

        for i, (drv1, drv2) in enumerate(driver_pairs, 1):
            cache_key = get_cache_key(year, race, session_type, drv1, drv2)
            cache_path = get_cache_path(cache_key)

            if cache_path.exists():
                stats['skipped'] += 1
                continue

            if dry_run:
                logging.info(f"  [{i}/{len(driver_pairs)}] Would cache: {drv1} vs {drv2}")
                stats['cached'] += 1
                continue

            try:
                # Need to reload session with telemetry for comparison
                if i == 1:  # Only load once
                    session.load()

                start = time.time()
                result = compare_fastest_laps(session, drv1, drv2)
                elapsed = time.time() - start

                cache_result(year, race, session_type, drv1, drv2, result)
                stats['cached'] += 1
                logging.info(f"  [{i}/{len(driver_pairs)}] {drv1} vs {drv2} ({elapsed:.1f}s)")

            except Exception as e:
                stats['failed'] += 1
                logging.warning(f"  [{i}/{len(driver_pairs)}] Failed {drv1} vs {drv2}: {e}")

    except Exception as e:
        logging.error(f"Failed to process race: {e}")

    return stats


def warm_year(year: int, session_type: str = 'Q',
              top_drivers_only: bool = False, dry_run: bool = False) -> dict:
    """Warm all races for a year."""
    logging.info(f"\n{'#'*60}")
    logging.info(f"# WARMING YEAR: {year}")
    logging.info(f"{'#'*60}")

    total_stats = {'cached': 0, 'skipped': 0, 'failed': 0, 'races': 0}

    try:
        races = get_races_cached(year)

        # Filter out future races
        current_year = datetime.now().year
        if year == current_year:
            remaining = set(fastf1.get_events_remaining()['EventName'])
            races = [r for r in races if r not in remaining]

        logging.info(f"Found {len(races)} completed races")

        for race in races:
            stats = warm_race(year, race, session_type, top_drivers_only, dry_run)
            total_stats['cached'] += stats['cached']
            total_stats['skipped'] += stats['skipped']
            total_stats['failed'] += stats['failed']
            total_stats['races'] += 1

    except Exception as e:
        logging.error(f"Failed to warm year {year}: {e}")

    return total_stats


def main():
    parser = argparse.ArgumentParser(description='Pre-warm the comparison cache')
    parser.add_argument('--year', type=int, help='Specific year to warm')
    parser.add_argument('--race', type=str, help='Specific race to warm')
    parser.add_argument('--all', action='store_true', help='Warm all years (2020-2025)')
    parser.add_argument('--session', type=str, default='Q', choices=['Q', 'R'],
                        help='Session type: Q=Qualifying, R=Race')
    parser.add_argument('--top-drivers', action='store_true',
                        help='Only cache top drivers per season')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be cached without caching')
    args = parser.parse_args()

    # Initialize FastF1 cache
    initialize_fastf1_cache('fastf1_cache')

    print("\n" + "="*60)
    print("F1 Telemetry Cache Warming")
    print("="*60)

    # Get current cache stats
    stats = get_cache_stats()
    print(f"\nCurrent cache: {stats['cached_comparisons']} comparisons ({stats['cache_size_mb']:.1f} MB)")
    print(f"Hit rate: {stats['hit_rate']*100:.1f}%")

    start_time = time.time()

    if args.race and args.year:
        # Warm specific race
        warm_race(args.year, args.race, args.session, args.top_drivers, args.dry_run)
    elif args.year:
        # Warm specific year
        warm_year(args.year, args.session, args.top_drivers, args.dry_run)
    elif args.all:
        # Warm all years
        for year in range(2020, 2026):
            warm_year(year, args.session, args.top_drivers, args.dry_run)
    else:
        # Default: warm 2024 and 2025
        for year in [2024, 2025]:
            warm_year(year, args.session, args.top_drivers, args.dry_run)

    elapsed = time.time() - start_time

    # Final stats
    stats = get_cache_stats()
    print("\n" + "="*60)
    print("WARMING COMPLETE")
    print("="*60)
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Cache now: {stats['cached_comparisons']} comparisons ({stats['cache_size_mb']:.1f} MB)")
    print(f"Hit rate: {stats['hit_rate']*100:.1f}%")


if __name__ == '__main__':
    main()
