"""
Enhanced Session Manager for F1 Telemetry Application

Manages FastF1 session loading with smart caching, analytics, and performance optimization.
🔥 UPGRADED with smart preloading based on user behavior and F1 calendar
"""

import fastf1
import logging
import os
from threading import Lock, Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple, List, Optional
import time
from functools import lru_cache
from datetime import datetime, timedelta


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


class SmartSessionManager:
    """
    🔥 ENHANCED: Thread-safe session manager with smart analytics and learning capabilities.
    
    New Features:
    - Smart preloading based on user behavior
    - F1 calendar awareness for upcoming races
    - Preload effectiveness tracking
    - Continuous learning from request patterns
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
        
        # Basic statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._preload_count = 0
        
        # 🔥 NEW: Smart analytics tracking
        self._session_analytics = {
            'hits': {},                    # (year, race, session) -> count
            'request_times': [],           # [(key, timestamp), ...]  
            'preload_effectiveness': {},   # track which preloads get used
            'calendar_data': None,         # cached F1 calendar
            'last_calendar_update': 0      # timestamp
        }
        
        logging.info(f"🧠 SmartSessionManager initialized with {max_workers} workers, "
                    f"preloading={'enabled' if enable_preloading else 'disabled'}, smart analytics enabled")
        
        # Start smart preloading if enabled
        if enable_preloading:
            self._start_smart_preloading()
    
    def get_session(self, year: int, race: str, session_type: str):
        """
        🔥 ENHANCED: Get a session with smart analytics tracking
        
        Args:
            year: Race year
            race: Race name
            session_type: 'Q' for Qualifying, 'R' for Race
        
        Returns:
            FastF1 session object
        """
        cache_key = (year, race, session_type)
        current_time = time.time()
        
        # Check cache first
        with self._cache_lock:
            if cache_key in self._session_cache:
                self._cache_hits += 1
                
                # 🔥 NEW: Track successful hits for analytics
                self._session_analytics['hits'][cache_key] = self._session_analytics['hits'].get(cache_key, 0) + 1
                self._session_analytics['request_times'].append((cache_key, current_time))

                # Limit request_times to prevent unbounded growth
                if len(self._session_analytics['request_times']) > 1000:
                    self._session_analytics['request_times'] = self._session_analytics['request_times'][-1000:]

                # Track preload effectiveness
                if cache_key in self._session_analytics['preload_effectiveness']:
                    self._session_analytics['preload_effectiveness'][cache_key]['used'] = True
                    self._session_analytics['preload_effectiveness'][cache_key]['first_use_time'] = min(
                        self._session_analytics['preload_effectiveness'][cache_key].get('first_use_time', current_time),
                        current_time
                    )
                
                hit_count = self._session_analytics['hits'][cache_key]
                logging.info(f"🎯 Cache hit: {year} {race} {session_type} (hit #{hit_count})")
                return self._session_cache[cache_key]
        
        # Not in cache, load it
        self._cache_misses += 1
        logging.info(f"❌ Cache miss: {year} {race} {session_type}")

        # 🔥 NEW: This counts as a "demand" for this session type
        self._session_analytics['hits'][cache_key] = self._session_analytics['hits'].get(cache_key, 0) + 1
        self._session_analytics['request_times'].append((cache_key, current_time))

        # Limit request_times to prevent unbounded growth
        if len(self._session_analytics['request_times']) > 1000:
            self._session_analytics['request_times'] = self._session_analytics['request_times'][-1000:]

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
                    logging.info(f"♻️  Evicted from cache: {oldest_key}")
                
                self._session_cache[cache_key] = session
            
            action = "preloaded" if is_preload else "loaded"
            logging.info(f"✅ Successfully {action}: {year} {race} {session_type}")
            return session
            
        except Exception as e:
            logging.error(f"💥 Failed to load session {year} {race} {session_type}: {e}")
            raise
    
    def _start_smart_preloading(self):
        """🔥 ENHANCED: Start smart preloading based on analytics and F1 calendar"""
        
        def smart_preload_worker():
            # Get smart candidates instead of hardcoded list
            candidates = self._get_smart_preload_candidates(max_candidates=5)
            
            logging.info(f"🧠 Smart preloading {len(candidates)} sessions based on analytics")
            
            for year, race, session_type in candidates:
                try:
                    # Track that we're preloading this session
                    cache_key = (year, race, session_type)
                    self._session_analytics['preload_effectiveness'][cache_key] = {
                        'preloaded_at': time.time(),
                        'used': False,
                        'first_use_time': None
                    }
                    
                    self._load_session_internal(year, race, session_type, is_preload=True)
                    self._preload_count += 1
                    logging.info(f"✅ Smart preloaded: {year} {race} {session_type}")
                    
                except Exception as e:
                    logging.warning(f"❌ Failed to preload {year} {race} {session_type}: {e}")
        
        # Submit smart preloading task
        self._executor.submit(smart_preload_worker)
    
    def _get_smart_preload_candidates(self, max_candidates: int = 5) -> List[Tuple]:
        """
        🔥 NEW: Get smart preload candidates based on analytics and F1 calendar
        
        Uses 3-factor scoring:
        - Frequency Score (40%): How often this session is requested
        - Recency Score (30%): Recent requests weighted higher
        - Calendar Score (30%): Upcoming races get priority
        """
        current_time = time.time()
        candidates_with_scores = []
        
        # If no analytics yet, use intelligent defaults
        if not self._session_analytics['hits']:
            return self._get_intelligent_defaults()
        
        # Calculate scores for each session we have data on
        total_hits = sum(self._session_analytics['hits'].values())
        
        for session_key, hit_count in self._session_analytics['hits'].items():
            year, race, session_type = session_key
            
            # 1. Frequency Score (40% weight) - how often requested
            frequency_score = hit_count / total_hits
            
            # 2. Recency Score (30% weight) - recent requests matter more
            recent_requests = [
                timestamp for key, timestamp in self._session_analytics['request_times']
                if key == session_key and current_time - timestamp < 604800  # Last 7 days
            ]
            recency_score = len(recent_requests) / max(1, hit_count) if hit_count > 0 else 0
            
            # 3. Calendar Proximity Score (30% weight) - upcoming races get bonus
            calendar_score = self._calculate_calendar_proximity_score(year, race)
            
            # Combine scores
            total_score = (frequency_score * 0.4 + 
                          recency_score * 0.3 + 
                          calendar_score * 0.3)
            
            candidates_with_scores.append((session_key, total_score, {
                'frequency': frequency_score,
                'recency': recency_score, 
                'calendar': calendar_score,
                'hits': hit_count
            }))
        
        # Sort by total score and return top candidates
        candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Log the decision making
        logging.info("🧠 Smart preload candidate scoring:")
        for i, (key, score, breakdown) in enumerate(candidates_with_scores[:max_candidates]):
            logging.info(f"  {i+1}. {key}: {score:.3f} "
                        f"(freq:{breakdown['frequency']:.3f}, recent:{breakdown['recency']:.3f}, "
                        f"calendar:{breakdown['calendar']:.3f}, hits:{breakdown['hits']})")
        
        return [candidate[0] for candidate in candidates_with_scores[:max_candidates]]
    
    def _get_intelligent_defaults(self) -> List[Tuple]:
        """🔥 NEW: Intelligent defaults when no analytics available yet"""
        current_year = datetime.now().year
        
        # Focus on current year + popular tracks
        defaults = [
            (current_year, "Monaco Grand Prix", "Q"),      # Always popular
            (current_year, "British Grand Prix", "Q"),     # Home race effect  
            (current_year, "Italian Grand Prix", "Q"),     # Monza always popular
            (current_year - 1, "Monaco Grand Prix", "Q"),  # Historical comparison
            (current_year, "Abu Dhabi Grand Prix", "Q"),   # Season finale
        ]
        
        logging.info(f"🎯 Using intelligent defaults for year {current_year}")
        return defaults
    
    def _calculate_calendar_proximity_score(self, year: int, race_name: str) -> float:
        """🔥 NEW: Calculate how close this race is to current F1 calendar"""
        try:
            current_time = time.time()
            
            # Update calendar cache if needed (once per day)
            if (current_time - self._session_analytics['last_calendar_update'] > 86400 or 
                self._session_analytics['calendar_data'] is None):
                
                try:
                    schedule = fastf1.get_event_schedule(datetime.now().year)
                    self._session_analytics['calendar_data'] = schedule
                    self._session_analytics['last_calendar_update'] = current_time
                    logging.info("📅 Updated F1 calendar cache")
                except Exception as e:
                    logging.warning(f"Failed to update calendar: {e}")
                    return 0.2  # Default moderate score
            
            # Find this race in the calendar
            schedule = self._session_analytics['calendar_data']
            if schedule is not None:
                race_events = schedule[schedule['EventName'] == race_name]
                if not race_events.empty:
                    race_date = race_events.iloc[0]['EventDate']
                    days_until_race = (race_date - datetime.now()).days
                    
                    # Races in next 30 days get highest score
                    if 0 <= days_until_race <= 30:
                        return 1.0
                    # Races in next 60 days get high score  
                    elif 31 <= days_until_race <= 60:
                        return 0.7
                    # Recent races (last 14 days) get medium score
                    elif -14 <= days_until_race < 0:
                        return 0.5
                    else:
                        return 0.1
            
            return 0.2  # Default if calendar lookup fails
            
        except Exception as e:
            logging.warning(f"Calendar proximity calculation failed: {e}")
            return 0.2
    
    def get_cache_stats(self) -> Dict:
        """🔥 ENHANCED: Get comprehensive cache statistics with smart analytics"""
        with self._cache_lock:
            # Calculate preload effectiveness
            preload_stats = {}
            total_preloaded = len(self._session_analytics['preload_effectiveness'])
            used_preloads = sum(1 for stats in self._session_analytics['preload_effectiveness'].values() 
                               if stats['used'])
            
            if total_preloaded > 0:
                preload_stats = {
                    'preload_hit_rate': used_preloads / total_preloaded,
                    'preloaded_sessions': total_preloaded,
                    'used_preloads': used_preloads,
                    'wasted_preloads': total_preloaded - used_preloads,
                    'effectiveness_percentage': f"{(used_preloads / total_preloaded) * 100:.1f}%"
                }
            
            # Top requested sessions
            top_sessions = sorted(
                self._session_analytics['hits'].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            
            return {
                # Existing stats
                "cache_size": len(self._session_cache),
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0,
                "preloaded_sessions": self._preload_count,
                "cached_sessions": list(self._session_cache.keys()),
                
                # 🔥 NEW: Smart analytics
                "preload_effectiveness": preload_stats,
                "top_requested_sessions": top_sessions,
                "total_unique_sessions_requested": len(self._session_analytics['hits']),
                "analytics_data_points": len(self._session_analytics['request_times']),
                "calendar_last_updated": datetime.fromtimestamp(self._session_analytics['last_calendar_update']).isoformat() if self._session_analytics['last_calendar_update'] > 0 else "Never"
            }
    
    def clear_cache(self, keep_popular: bool = False):
        """Clear the session cache"""
        with self._cache_lock:
            if keep_popular:
                # Keep sessions that have been requested recently
                current_time = time.time()
                recent_sessions = set()
                
                for key, timestamp in self._session_analytics['request_times']:
                    if current_time - timestamp < 86400:  # Last 24 hours
                        recent_sessions.add(key)
                
                new_cache = {k: v for k, v in self._session_cache.items() if k in recent_sessions}
                self._session_cache = new_cache
                logging.info(f"♻️  Cache cleared, kept {len(new_cache)} recently used sessions")
            else:
                self._session_cache.clear()
                logging.info("♻️  Cache completely cleared")
    
    def preload_session(self, year: int, race: str, session_type: str):
        """Manually trigger preloading of a specific session"""
        cache_key = (year, race, session_type)
        
        with self._cache_lock:
            if cache_key in self._session_cache:
                logging.info(f"✅ Session already cached: {year} {race} {session_type}")
                return
        
        # Submit to thread pool
        future = self._executor.submit(self._load_session_internal, year, race, session_type, True)
        logging.info(f"⏳ Queued for preload: {year} {race} {session_type}")
        return future
    
    def get_smart_insights(self) -> Dict:
        """🔥 NEW: Get insights into user behavior and system performance"""
        with self._cache_lock:
            insights = {
                'most_popular_tracks': [],
                'most_popular_session_types': {},
                'usage_patterns': {},
                'optimization_suggestions': []
            }
            
            if not self._session_analytics['hits']:
                return insights
            
            # Track usage by track
            track_hits = {}
            session_type_hits = {'Q': 0, 'R': 0}
            
            for (year, race, session_type), count in self._session_analytics['hits'].items():
                track_hits[race] = track_hits.get(race, 0) + count
                session_type_hits[session_type] = session_type_hits.get(session_type, 0) + count
            
            insights['most_popular_tracks'] = sorted(track_hits.items(), key=lambda x: x[1], reverse=True)[:5]
            insights['most_popular_session_types'] = session_type_hits
            
            # Usage patterns
            total_requests = len(self._session_analytics['request_times'])
            unique_sessions = len(self._session_analytics['hits'])
            
            insights['usage_patterns'] = {
                'total_requests': total_requests,
                'unique_sessions_requested': unique_sessions,
                'average_requests_per_session': total_requests / max(1, unique_sessions),
                'cache_efficiency': self._cache_hits / max(1, self._cache_hits + self._cache_misses)
            }
            
            # Optimization suggestions
            if insights['usage_patterns']['cache_efficiency'] < 0.5:
                insights['optimization_suggestions'].append("Consider increasing cache size - low hit rate detected")
            
            if session_type_hits['Q'] > session_type_hits['R'] * 2:
                insights['optimization_suggestions'].append("Users prefer Qualifying - prioritize Q sessions for preloading")
            
            return insights
    
    def shutdown(self):
        """Shutdown the session manager"""
        self._executor.shutdown(wait=True)
        logging.info("🔥 SmartSessionManager shutdown complete")


# For backward compatibility, create an alias
SessionManager = SmartSessionManager
