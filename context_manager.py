"""
Context Manager for F1 Telemetry Application

Manages request-scoped telemetry contexts to support concurrent users.
🔥 NEW: Replaces global current_telemetry_context with thread-safe session management
"""

import threading
import time
import uuid
import gc
from typing import Dict, Optional
from contextlib import contextmanager
import matplotlib.pyplot as plt
import logging


class TelemetryContextManager:
    """
    🔥 NEW: Thread-safe context manager for telemetry data
    
    Replaces the global current_telemetry_context with session-based storage
    that supports multiple concurrent users.
    """
    
    def __init__(self, ttl_seconds: int = 1800):  # 30 minutes default TTL
        self._contexts: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._cleanup_interval = 300  # Clean up every 5 minutes
        self._last_cleanup = time.time()
        
        logging.info(f"🔐 TelemetryContextManager initialized with {ttl_seconds}s TTL")
    
    def create_session(self) -> str:
        """Create a new session ID for a user"""
        session_id = str(uuid.uuid4())
        logging.info(f"🆔 Created new session: {session_id[:8]}...")
        return session_id
    
    def set_context(self, session_id: str, context: dict):
        """Store telemetry context for a specific session"""
        current_time = time.time()
        
        with self._lock:
            self._contexts[session_id] = {
                'data': context,
                'created_at': current_time,
                'last_accessed': current_time,
                'size_estimate': len(str(context))  # Rough size estimate
            }
            
            # Trigger cleanup if needed
            if current_time - self._last_cleanup > self._cleanup_interval:
                self._cleanup_expired()
        
        logging.info(f"💾 Stored context for session {session_id[:8]}... "
                    f"(~{len(str(context))} chars)")
    
    def get_context(self, session_id: str) -> Optional[dict]:
        """Retrieve telemetry context for a specific session"""
        with self._lock:
            if session_id in self._contexts:
                # Update last accessed time
                self._contexts[session_id]['last_accessed'] = time.time()
                context_data = self._contexts[session_id]['data']
                
                logging.info(f"📖 Retrieved context for session {session_id[:8]}...")
                return context_data
        
        logging.warning(f"❌ No context found for session {session_id[:8]}...")
        return None
    
    def delete_context(self, session_id: str):
        """Explicitly delete a session context"""
        with self._lock:
            if session_id in self._contexts:
                del self._contexts[session_id] 
                logging.info(f"🗑️  Deleted context for session {session_id[:8]}...")
    
    def _cleanup_expired(self):
        """Remove expired contexts (called automatically)"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, context_info in self._contexts.items():
            if current_time - context_info['last_accessed'] > self._ttl:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self._contexts[session_id]
        
        self._last_cleanup = current_time
        
        if expired_sessions:
            logging.info(f"🧹 Cleaned up {len(expired_sessions)} expired contexts")
    
    def get_stats(self) -> dict:
        """Get statistics about context usage"""
        with self._lock:
            total_size = sum(ctx['size_estimate'] for ctx in self._contexts.values())
            active_sessions = len(self._contexts)
            
            return {
                'active_sessions': active_sessions,
                'total_memory_estimate': f"{total_size / 1024:.1f} KB",
                'oldest_session_age': max(
                    [(time.time() - ctx['created_at']) / 60 for ctx in self._contexts.values()],
                    default=[0]
                )[0] if self._contexts else 0,
                'ttl_minutes': self._ttl / 60
            }
    
    def force_cleanup(self):
        """Force cleanup of all expired contexts"""
        with self._lock:
            self._cleanup_expired()


@contextmanager
def managed_figure(figsize=(28, 20), nrows=5, ncols=1, facecolor="#111"):
    """
    🔥 NEW: Context manager for matplotlib figures to prevent memory leaks
    
    Usage:
    with managed_figure((28, 20), 5, 1) as (fig, axes):
        # Plot generation here
        # Automatic cleanup guaranteed
    """
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize)
    fig.patch.set_facecolor(facecolor)
    
    try:
        yield fig, axes
    finally:
        # Aggressive cleanup to prevent memory leaks
        plt.close(fig)
        del fig, axes
        gc.collect()  # Force garbage collection


@contextmanager 
def telemetry_session(context_manager: TelemetryContextManager, context_data: dict = None):
    """
    🔥 NEW: Context manager for telemetry sessions
    
    Usage:
    with telemetry_session(context_manager, my_context) as session_id:
        # Use session_id for this request
        # Automatic cleanup when done
    """
    session_id = context_manager.create_session()
    
    try:
        if context_data:
            context_manager.set_context(session_id, context_data)
        yield session_id
    finally:
        # Clean up the session when done
        context_manager.delete_context(session_id)


class MemoryOptimizedTelemetryProcessor:
    """
    🔥 NEW: Optimized telemetry data processing to reduce memory usage
    
    Replaces multiple data copies with views and in-place operations
    """
    
    @staticmethod
    def get_optimized_telemetry(fastest_lap, required_columns=None):
        """
        Get telemetry data with minimal memory footprint
        
        Args:
            fastest_lap: FastF1 lap object
            required_columns: List of columns to include (reduces memory)
        
        Returns:
            Optimized telemetry dataframe
        """
        if required_columns is None:
            required_columns = ['Time', 'Distance', 'Speed', 'Throttle', 'Brake', 'RPM', 'nGear']
        
        # Get base telemetry
        tel = fastest_lap.get_telemetry()
        
        # Add distance in-place if not present
        if 'Distance' not in tel.columns:
            tel = tel.add_distance()
        
        # Return only required columns (view, not copy)
        return tel[required_columns].copy()  # Single copy with only needed data
    
    @staticmethod
    def create_interpolation_arrays(drv1_tel, drv2_tel, num_points=1500):
        """
        Create common interpolation arrays with memory optimization
        
        Returns:
            tuple: (common_distance_array, drv1_interpolated, drv2_interpolated)
        """
        # Find common distance range
        min_dist = max(drv1_tel["Distance"].min(), drv2_tel["Distance"].min())
        max_dist = min(drv1_tel["Distance"].max(), drv2_tel["Distance"].max())
        
        # Create common distance array
        common_dist = np.linspace(min_dist, max_dist, num_points)
        
        # Pre-allocate arrays for better memory efficiency
        import numpy as np
        interpolated_data = {
            'drv1': {},
            'drv2': {},
            'common_dist': common_dist
        }
        
        # Interpolate required channels
        channels = ['Time', 'Speed', 'Throttle', 'Brake', 'RPM', 'nGear']
        
        for channel in channels:
            if channel in drv1_tel.columns:
                if channel == 'Time':
                    # Convert time to seconds for interpolation
                    drv1_time_seconds = drv1_tel[channel].dt.total_seconds()
                    drv2_time_seconds = drv2_tel[channel].dt.total_seconds()
                    interpolated_data['drv1'][channel] = np.interp(common_dist, drv1_tel["Distance"], drv1_time_seconds)
                    interpolated_data['drv2'][channel] = np.interp(common_dist, drv2_tel["Distance"], drv2_time_seconds)
                else:
                    interpolated_data['drv1'][channel] = np.interp(common_dist, drv1_tel["Distance"], drv1_tel[channel])
                    interpolated_data['drv2'][channel] = np.interp(common_dist, drv2_tel["Distance"], drv2_tel[channel])
        
        return interpolated_data
    
    @staticmethod
    def cleanup_telemetry_data(*data_objects):
        """Clean up telemetry data objects to free memory"""
        for obj in data_objects:
            if hasattr(obj, 'clear'):
                obj.clear()
            del obj
        gc.collect()


# Global context manager instance
global_context_manager = TelemetryContextManager()


# Utility functions for easy integration
def get_session_context(session_id: str) -> Optional[dict]:
    """Get context for a session (helper function)"""
    return global_context_manager.get_context(session_id)


def set_session_context(session_id: str, context: dict):
    """Set context for a session (helper function)"""
    global_context_manager.set_context(session_id, context)


def create_user_session() -> str:
    """Create a new user session (helper function)"""
    return global_context_manager.create_session()
