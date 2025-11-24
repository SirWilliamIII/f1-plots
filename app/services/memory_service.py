"""
Memory Management Service

Handles memory monitoring, garbage collection, and memory usage tracking.
"""

import gc
import psutil
import logging
import tracemalloc
from datetime import datetime


def force_garbage_collection():
    """Force garbage collection and return memory freed"""
    before = psutil.Process().memory_info().rss
    gc.collect()
    after = psutil.Process().memory_info().rss
    freed_mb = (before - after) / (1024 * 1024)
    return freed_mb


def check_memory_usage():
    """Check current memory usage and trigger cleanup if needed"""
    from config import FLASK_CONFIG
    current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
    if current_memory > FLASK_CONFIG.memory_threshold_mb:
        freed = force_garbage_collection()
        logging.info(f"Memory cleanup: freed {freed:.1f}MB, current: {current_memory:.1f}MB")
        return True
    return False


def cleanup_matplotlib():
    """Clean up matplotlib resources"""
    import matplotlib.pyplot as plt
    plt.close('all')
    gc.collect()


class MemoryMonitor:
    """Monitor memory usage and collect statistics"""

    def __init__(self):
        self.process = psutil.Process()
        self.start_time = datetime.now()
        self.memory_samples = []
        self.max_samples = 100  # Reduced from 1000 to save memory
        tracemalloc.start()

    def get_memory_info(self):
        """Get current memory usage information"""
        memory_info = self.process.memory_info()
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': self.process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024,
            'swap_used_mb': psutil.swap_memory().used / 1024 / 1024,
        }

    def get_top_allocations(self, limit=10):
        """Get top memory allocations"""
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        return [
            {
                'file': stat.traceback.format()[0],
                'size_mb': stat.size / 1024 / 1024,
                'count': stat.count
            }
            for stat in top_stats[:limit]
        ]

    def record_sample(self):
        """Record a memory usage sample"""
        sample = {
            'timestamp': datetime.now().isoformat(),
            'memory': self.get_memory_info()
        }
        self.memory_samples.append(sample)
        # Keep only the most recent samples to prevent unbounded growth
        if len(self.memory_samples) > self.max_samples:
            self.memory_samples = self.memory_samples[-self.max_samples:]
        return sample


# Initialize global memory monitor
memory_monitor = MemoryMonitor()
