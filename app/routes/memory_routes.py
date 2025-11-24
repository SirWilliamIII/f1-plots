"""
Memory Monitoring Routes

Handles memory status and monitoring endpoints.
"""

import gc
import logging
import threading
import time
from datetime import datetime
from flask import jsonify
from app.services.memory_service import memory_monitor
from app.services.context_service import cleanup_old_contexts


# Background thread to collect memory samples
def memory_sampling_thread():
    """Background thread that samples memory usage every minute"""
    while True:
        try:
            memory_monitor.record_sample()
            time.sleep(60)  # Sample every minute
        except Exception as e:
            logging.error(f"Memory sampling error: {e}")


# Periodic cleanup thread to prevent memory accumulation
def periodic_cleanup_thread():
    """Background thread that runs cleanup every 30 minutes"""
    while True:
        try:
            time.sleep(1800)  # Every 30 minutes
            cleanup_old_contexts()
            gc.collect()
            logging.info("♻️  Periodic cleanup completed")
        except Exception as e:
            logging.error(f"Periodic cleanup error: {e}")


def register_memory_routes(app):
    """Register memory monitoring routes and start background threads"""

    # Start memory sampling thread
    sampling_thread = threading.Thread(target=memory_sampling_thread, daemon=True)
    sampling_thread.start()

    # Start periodic cleanup thread
    cleanup_thread = threading.Thread(target=periodic_cleanup_thread, daemon=True)
    cleanup_thread.start()
    logging.info("🧹 Periodic cleanup thread started (runs every 30 minutes)")

    @app.route('/memory_status')
    def memory_status():
        """Endpoint to check current memory usage"""
        try:
            current = memory_monitor.get_memory_info()
            top_allocations = memory_monitor.get_top_allocations()

            # Force garbage collection
            gc.collect()
            after_gc = memory_monitor.get_memory_info()

            return jsonify({
                'current_memory': current,
                'after_gc': after_gc,
                'gc_freed_mb': current['rss_mb'] - after_gc['rss_mb'],
                'top_allocations': top_allocations,
                'uptime_minutes': (datetime.now() - memory_monitor.start_time).total_seconds() / 60,
                'sample_count': len(memory_monitor.memory_samples)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/memory_history')
    def memory_history():
        """Get memory usage history"""
        return jsonify({
            'samples': memory_monitor.memory_samples[-100:]  # Last 100 samples
        })

    @app.route('/force_gc', methods=['POST'])
    def force_gc():
        """Force garbage collection"""
        before = memory_monitor.get_memory_info()
        gc.collect()
        after = memory_monitor.get_memory_info()

        return jsonify({
            'before': before,
            'after': after,
            'freed_mb': before['rss_mb'] - after['rss_mb']
        })
