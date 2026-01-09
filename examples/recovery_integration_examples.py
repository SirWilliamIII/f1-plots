"""
Recovery Manager Integration Examples

Demonstrates how to integrate the RecoveryManager into various parts of the application.
"""

import logging
import requests
from typing import Optional
from app.error_tracking import (
    get_recovery_manager,
    get_error_tracker,
    ErrorType,
    with_recovery,
    classify_error,
    recover_ollama_error,
    recover_fastf1_error,
    recover_plot_generation_error
)

logger = logging.getLogger(__name__)


# ========================================
# Example 1: Ollama API Integration
# ========================================

def call_ollama_with_recovery(prompt: str, model: str = "qwen2.5-coder:7b") -> dict:
    """
    Call Ollama API with full recovery strategy.

    Features:
    - Circuit breaker protection
    - Exponential backoff retry
    - Fallback response if service unavailable
    """
    recovery_manager = get_recovery_manager(get_error_tracker())

    def call_ollama():
        import os
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11435")

        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    return recovery_manager.execute_with_recovery(
        func=call_ollama,
        service_name='ollama',
        error_type=ErrorType.API_ERROR,
        fallback=lambda ctx: recover_ollama_error(None, ctx),
        context={'prompt': prompt, 'model': model}
    )


# Alternative: Using decorator
@with_recovery('ollama', ErrorType.API_ERROR, fallback=lambda: recover_ollama_error(None))
def call_ollama_decorated(prompt: str, model: str = "qwen2.5-coder:7b") -> dict:
    """Same as above but using decorator pattern"""
    import os
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11435")

    response = requests.post(
        f"{ollama_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        },
        timeout=30
    )
    response.raise_for_status()
    return response.json()


# ========================================
# Example 2: FastF1 Session Loading
# ========================================

def load_session_with_recovery(session_manager, year: int, race: str, session_type: str):
    """
    Load FastF1 session with recovery strategy.

    Features:
    - Network error retry with backoff
    - Cache fallback if download fails
    - Automatic error tracking
    """
    recovery_manager = get_recovery_manager(get_error_tracker())
    error_tracker = get_error_tracker()

    cache_key = (year, race, session_type)

    def load_session():
        try:
            return session_manager._load_session_internal(year, race, session_type)
        except Exception as e:
            # Classify error type
            error_type = classify_error(e)
            logger.warning(f"FastF1 error classified as: {error_type.value}")

            # Track error
            error_tracker.capture_exception(
                e,
                context={
                    'year': year,
                    'race': race,
                    'session_type': session_type,
                    'error_type': error_type.value
                }
            )
            raise

    def fallback_to_cache(ctx):
        return recover_fastf1_error(
            None,
            context={
                'session_manager': session_manager,
                'cache_key': cache_key
            }
        )

    return recovery_manager.execute_with_recovery(
        func=load_session,
        service_name='fastf1',
        error_type=ErrorType.NETWORK_ERROR,
        fallback=fallback_to_cache,
        context={
            'session_manager': session_manager,
            'cache_key': cache_key
        }
    )


# ========================================
# Example 3: Plot Generation
# ========================================

def generate_plot_with_recovery(session, driver1: str, driver2: str):
    """
    Generate telemetry plot with recovery strategy.

    Features:
    - Memory monitoring
    - Automatic cleanup on memory errors
    - Fallback error plot
    """
    recovery_manager = get_recovery_manager(get_error_tracker())

    def generate_plot():
        # Check memory before plotting
        recovery_manager.handle_memory_error(threshold_mb=300)

        # Import here to avoid circular dependencies
        from app.plotting.telemetry_plots import compare_fastest_laps

        return compare_fastest_laps(session, driver1, driver2)

    def fallback_plot(ctx):
        return recover_plot_generation_error(None, ctx)

    try:
        result = recovery_manager.execute_with_recovery(
            func=generate_plot,
            service_name='fastf1',  # Plot generation depends on FastF1 data
            error_type=ErrorType.DATA_ERROR,
            fallback=fallback_plot,
            context={'driver1': driver1, 'driver2': driver2}
        )

        # Force memory cleanup after plot generation
        recovery_manager.handle_memory_error(threshold_mb=300)

        return result

    except Exception as e:
        logger.error(f"Plot generation failed: {e}")
        # Return minimal fallback plot
        return fallback_plot({'driver1': driver1, 'driver2': driver2})


# ========================================
# Example 4: Modal GPU Function Call
# ========================================

def call_modal_gpu_with_recovery(prompt: str, model: str = "qwen2.5-coder:7b") -> dict:
    """
    Call Modal GPU function with recovery strategy.

    Features:
    - Circuit breaker for Modal service
    - Timeout handling
    - Fallback to local Ollama if Modal unavailable
    """
    recovery_manager = get_recovery_manager(get_error_tracker())

    def call_modal():
        import modal
        generate_fn = modal.Function.from_name("f1-ollama-gpu", "generate")

        return generate_fn.remote(
            model=model,
            prompt=prompt,
            temperature=0.1
        )

    def fallback_to_local(ctx):
        logger.info("Modal GPU unavailable, falling back to local Ollama")
        try:
            return call_ollama_with_recovery(prompt, model)
        except Exception as e:
            logger.error(f"Local fallback also failed: {e}")
            return recover_ollama_error(e, ctx)

    return recovery_manager.execute_with_recovery(
        func=call_modal,
        service_name='modal',
        error_type=ErrorType.API_ERROR,
        fallback=fallback_to_local,
        context={'prompt': prompt, 'model': model}
    )


# ========================================
# Example 5: Multi-Service Request
# ========================================

def analyze_telemetry_moment_with_recovery(
    session_manager,
    year: int,
    race: str,
    session_type: str,
    driver1: str,
    driver2: str,
    moment_time: float
) -> dict:
    """
    Complete telemetry analysis with multi-level recovery.

    This example shows how to chain multiple recovery strategies:
    1. Load session (FastF1 + network retry)
    2. Generate plot (memory management)
    3. AI analysis (Ollama + circuit breaker)
    """
    recovery_manager = get_recovery_manager(get_error_tracker())
    error_tracker = get_error_tracker()

    result = {
        'session_loaded': False,
        'plot_generated': False,
        'ai_analysis': None,
        'errors': []
    }

    try:
        # Step 1: Load session with recovery
        logger.info(f"Loading session: {year} {race} {session_type}")
        session = load_session_with_recovery(session_manager, year, race, session_type)
        result['session_loaded'] = True

    except Exception as e:
        error_tracker.capture_exception(e, context={'step': 'session_loading'})
        result['errors'].append(f"Session loading failed: {str(e)}")
        return result

    try:
        # Step 2: Generate plot with recovery
        logger.info(f"Generating plot: {driver1} vs {driver2}")
        plot_result = generate_plot_with_recovery(session, driver1, driver2)
        result['plot_generated'] = True
        result['plot_data'] = plot_result

    except Exception as e:
        error_tracker.capture_exception(e, context={'step': 'plot_generation'})
        result['errors'].append(f"Plot generation failed: {str(e)}")
        # Continue to AI analysis even if plot fails

    try:
        # Step 3: AI analysis with recovery
        logger.info(f"Analyzing moment at {moment_time}s")

        prompt = f"""
        Analyze telemetry moment at {moment_time}s for {driver1} vs {driver2}
        in {year} {race} {session_type}.
        """

        ai_result = call_modal_gpu_with_recovery(prompt)
        result['ai_analysis'] = ai_result

    except Exception as e:
        error_tracker.capture_exception(e, context={'step': 'ai_analysis'})
        result['errors'].append(f"AI analysis failed: {str(e)}")

    return result


# ========================================
# Example 6: Custom Error Classification
# ========================================

def handle_custom_error_with_recovery(operation: callable, *args, **kwargs):
    """
    Generic error handler with automatic classification and recovery.

    This is the most flexible pattern - automatically classifies errors
    and applies appropriate recovery strategy.
    """
    recovery_manager = get_recovery_manager(get_error_tracker())
    error_tracker = get_error_tracker()

    try:
        return operation(*args, **kwargs)

    except Exception as e:
        # Automatically classify the error
        error_type = classify_error(e)

        logger.warning(f"Error occurred: {type(e).__name__} (classified as {error_type.value})")

        # Track error
        error_tracker.capture_exception(
            e,
            context={
                'operation': operation.__name__,
                'error_type': error_type.value
            }
        )

        # Apply recovery based on error type
        if error_type == ErrorType.MEMORY_ERROR:
            logger.info("Memory error detected, triggering cleanup")
            recovery_manager.handle_memory_error()
            # Retry after cleanup
            return operation(*args, **kwargs)

        elif error_type == ErrorType.NETWORK_ERROR:
            logger.info("Network error detected, retrying with backoff")
            return recovery_manager.execute_with_recovery(
                func=operation,
                service_name='fastf1',  # Assume network error is FastF1
                error_type=error_type,
                *args,
                **kwargs
            )

        else:
            # Unknown error, re-raise
            logger.error(f"Unrecoverable error: {e}")
            raise


# ========================================
# Example 7: Monitoring and Alerting
# ========================================

def check_system_health() -> dict:
    """
    Check overall system health including recovery stats.

    Use this for monitoring endpoints or scheduled health checks.
    """
    recovery_manager = get_recovery_manager()
    error_tracker = get_error_tracker()

    health = {
        'status': 'healthy',
        'issues': [],
        'warnings': []
    }

    # Check recovery stats
    recovery_stats = recovery_manager.get_recovery_stats()

    # Check circuit breakers
    for name, cb_state in recovery_stats['circuit_breakers'].items():
        if cb_state['state'] == 'open':
            health['status'] = 'degraded'
            health['issues'].append(f"Circuit breaker OPEN for {name}")
        elif cb_state['state'] == 'half_open':
            health['warnings'].append(f"Circuit breaker HALF_OPEN for {name} (testing recovery)")

    # Check retry success rate
    if recovery_stats['retry_success_rate'] < 0.5 and recovery_stats['total_retries'] > 10:
        health['status'] = 'degraded'
        health['warnings'].append(
            f"Low retry success rate: {recovery_stats['retry_success_rate']:.1%}"
        )

    # Check error stats
    error_stats = error_tracker.get_error_stats()
    if error_stats['total_errors'] > 100:
        health['warnings'].append(f"High error count: {error_stats['total_errors']}")

    # Include stats
    health['recovery_stats'] = recovery_stats
    health['error_stats'] = error_stats

    return health


# ========================================
# Usage in Flask Routes
# ========================================

"""
Example integration in app/routes/api_routes.py:

from examples.recovery_integration_examples import load_session_with_recovery

@app.route("/get_drivers", methods=["POST"])
def get_drivers():
    data = request.json
    year = int(data["year"])
    race = data["race"]
    session_type = data["session"]

    try:
        # Use recovery-wrapped version
        session = load_session_with_recovery(session_manager, year, race, session_type)

        drivers = [
            {"value": drv, "label": f"{drv} ({session.get_driver(drv)['TeamName']})"}
            for drv in session.drivers
        ]

        return jsonify({"drivers": drivers}), 200

    except Exception as e:
        logger.error(f"Failed to get drivers: {e}")
        return jsonify({"error": str(e)}), 500
"""

if __name__ == "__main__":
    # Test examples
    import sys
    logging.basicConfig(level=logging.INFO)

    print("Testing error classification...")
    from requests.exceptions import ConnectionError, Timeout

    test_errors = [
        ConnectionError("Connection refused"),
        Timeout("Request timed out"),
        MemoryError("Out of memory"),
        ValueError("Invalid data"),
        Exception("Unknown error")
    ]

    for error in test_errors:
        error_type = classify_error(error)
        print(f"  {type(error).__name__}: {error_type.value}")

    print("\nRecovery Manager integration examples loaded successfully!")
    print("See function docstrings for usage patterns.")
