"""
Tests for RecoveryManager

Validates circuit breakers, retry policies, and error recovery strategies.
"""

import pytest
import time
from unittest.mock import Mock, patch
from app.error_tracking import (
    RecoveryManager,
    CircuitState,
    ErrorType,
    RetryPolicy,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    classify_error,
    recover_ollama_error,
    get_recovery_manager
)


class TestCircuitBreaker:
    """Test circuit breaker functionality"""

    def test_circuit_breaker_starts_closed(self):
        """Circuit breaker should start in CLOSED state"""
        recovery_manager = RecoveryManager()
        cb = recovery_manager.circuit_breakers['ollama']

        assert cb.state.state == CircuitState.CLOSED
        assert cb.state.failure_count == 0

    def test_circuit_breaker_opens_after_threshold(self):
        """Circuit breaker should open after failure threshold"""
        recovery_manager = RecoveryManager()
        cb = recovery_manager.circuit_breakers['ollama']

        # Force failures
        failing_func = Mock(side_effect=Exception("Service error"))

        for i in range(cb.config.failure_threshold):
            try:
                cb.call(failing_func)
            except Exception:
                pass

        # Should be OPEN now
        assert cb.state.state == CircuitState.OPEN

    def test_circuit_breaker_blocks_when_open(self):
        """Circuit breaker should block calls when OPEN"""
        recovery_manager = RecoveryManager()
        cb = recovery_manager.circuit_breakers['ollama']

        # Force circuit to open
        cb.state.state = CircuitState.OPEN
        cb.state.opened_at = time.time()

        # Should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "success")

    def test_circuit_breaker_transitions_to_half_open(self):
        """Circuit breaker should transition to HALF_OPEN after timeout"""
        recovery_manager = RecoveryManager()
        cb = recovery_manager.circuit_breakers['ollama']

        # Force circuit to open
        cb.state.state = CircuitState.OPEN
        cb.state.opened_at = time.time() - cb.config.timeout - 1  # Past timeout

        # Should allow call (HALF_OPEN)
        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state.state == CircuitState.HALF_OPEN

    def test_circuit_breaker_closes_after_successes(self):
        """Circuit breaker should close after success threshold in HALF_OPEN"""
        recovery_manager = RecoveryManager()
        cb = recovery_manager.circuit_breakers['ollama']

        # Set to HALF_OPEN
        cb.state.state = CircuitState.HALF_OPEN
        cb.state.success_count = 0

        # Make successful calls
        for i in range(cb.config.success_threshold):
            cb.call(lambda: "success")

        # Should be CLOSED now
        assert cb.state.state == CircuitState.CLOSED

    def test_circuit_breaker_reopens_on_failure_in_half_open(self):
        """Circuit breaker should reopen on failure in HALF_OPEN"""
        recovery_manager = RecoveryManager()
        cb = recovery_manager.circuit_breakers['ollama']

        # Set to HALF_OPEN
        cb.state.state = CircuitState.HALF_OPEN

        # Fail
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass

        # Should be OPEN again
        assert cb.state.state == CircuitState.OPEN

    def test_circuit_breaker_reset(self):
        """Reset should clear circuit breaker state"""
        recovery_manager = RecoveryManager()
        cb = recovery_manager.circuit_breakers['ollama']

        # Mess up state
        cb.state.state = CircuitState.OPEN
        cb.state.failure_count = 10

        # Reset
        cb.reset()

        # Should be back to initial state
        assert cb.state.state == CircuitState.CLOSED
        assert cb.state.failure_count == 0


class TestRetryPolicies:
    """Test retry policy behavior"""

    def test_network_error_retry_policy(self):
        """Network errors should have aggressive retry"""
        recovery_manager = RecoveryManager()
        policy = recovery_manager.retry_policies[ErrorType.NETWORK_ERROR]

        assert policy.max_attempts == 5
        assert policy.initial_delay == 0.5
        assert policy.jitter is True

    def test_memory_error_no_retry(self):
        """Memory errors should not retry"""
        recovery_manager = RecoveryManager()
        policy = recovery_manager.retry_policies[ErrorType.MEMORY_ERROR]

        assert policy.max_attempts == 1

    def test_exponential_backoff_calculation(self):
        """Backoff should increase exponentially"""
        recovery_manager = RecoveryManager()

        delays = []
        for attempt in range(5):
            delay = recovery_manager._calculate_backoff(
                attempt,
                initial_delay=1.0,
                max_delay=30.0,
                base=2.0,
                jitter=False
            )
            delays.append(delay)

        # Should be: 1, 2, 4, 8, 16
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0
        assert delays[3] == 8.0
        assert delays[4] == 16.0

    def test_backoff_respects_max_delay(self):
        """Backoff should not exceed max delay"""
        recovery_manager = RecoveryManager()

        delay = recovery_manager._calculate_backoff(
            attempt=10,
            initial_delay=1.0,
            max_delay=30.0,
            base=2.0,
            jitter=False
        )

        assert delay <= 30.0

    def test_backoff_with_jitter(self):
        """Jitter should add randomness to delay"""
        recovery_manager = RecoveryManager()

        # Run multiple times to check randomness
        delays = []
        for _ in range(10):
            delay = recovery_manager._calculate_backoff(
                attempt=2,
                initial_delay=1.0,
                max_delay=30.0,
                base=2.0,
                jitter=True
            )
            delays.append(delay)

        # All should be around 4s but not identical
        assert len(set(delays)) > 1  # Not all the same
        assert all(3.0 <= d <= 5.0 for d in delays)  # Within ±25%


class TestRecoveryExecution:
    """Test end-to-end recovery execution"""

    def test_successful_execution_no_recovery_needed(self):
        """Successful execution should not trigger recovery"""
        recovery_manager = RecoveryManager()

        func = Mock(return_value="success")

        result = recovery_manager.execute_with_recovery(
            func=func,
            service_name='ollama',
            error_type=ErrorType.API_ERROR
        )

        assert result == "success"
        assert func.call_count == 1
        assert recovery_manager.recovery_stats['total_retries'] == 0

    def test_retry_on_failure(self):
        """Failed calls should retry with backoff"""
        recovery_manager = RecoveryManager()

        # Fail twice, then succeed
        func = Mock(side_effect=[Exception("Fail 1"), Exception("Fail 2"), "success"])

        result = recovery_manager.execute_with_recovery(
            func=func,
            service_name='ollama',
            error_type=ErrorType.API_ERROR
        )

        assert result == "success"
        assert func.call_count == 3
        assert recovery_manager.recovery_stats['total_retries'] >= 2

    def test_fallback_on_exhausted_retries(self):
        """Fallback should execute when retries exhausted"""
        recovery_manager = RecoveryManager()

        func = Mock(side_effect=Exception("Always fails"))
        fallback = Mock(return_value="fallback_response")

        result = recovery_manager.execute_with_recovery(
            func=func,
            service_name='ollama',
            error_type=ErrorType.API_ERROR,
            fallback=fallback
        )

        assert result == "fallback_response"
        assert fallback.call_count == 1
        assert recovery_manager.recovery_stats['graceful_degradations'] == 1

    def test_circuit_breaker_integration(self):
        """Circuit breaker should block after failures"""
        recovery_manager = RecoveryManager()

        func = Mock(side_effect=Exception("Service down"))

        # Make enough calls to open circuit
        for i in range(5):
            try:
                recovery_manager.execute_with_recovery(
                    func=func,
                    service_name='ollama',
                    error_type=ErrorType.API_ERROR
                )
            except Exception:
                pass

        # Circuit should be open, next call should block
        cb = recovery_manager.circuit_breakers['ollama']
        assert cb.state.state == CircuitState.OPEN

        # Should use fallback immediately (not retry)
        fallback = Mock(return_value="fallback")
        result = recovery_manager.execute_with_recovery(
            func=func,
            service_name='ollama',
            error_type=ErrorType.API_ERROR,
            fallback=fallback
        )

        assert result == "fallback"
        assert recovery_manager.recovery_stats['circuit_breaker_blocks'] > 0


class TestErrorClassification:
    """Test error classification logic"""

    def test_classify_network_error(self):
        """Network errors should be classified correctly"""
        import requests

        error = requests.ConnectionError("Connection refused")
        error_type = classify_error(error)

        assert error_type == ErrorType.NETWORK_ERROR

    def test_classify_timeout_error(self):
        """Timeout errors should be classified correctly"""
        import requests

        error = requests.Timeout("Request timed out")
        error_type = classify_error(error)

        assert error_type == ErrorType.TIMEOUT_ERROR

    def test_classify_memory_error(self):
        """Memory errors should be classified correctly"""
        error = MemoryError("Out of memory")
        error_type = classify_error(error)

        assert error_type == ErrorType.MEMORY_ERROR

    def test_classify_data_error(self):
        """Data errors should be classified correctly"""
        error = KeyError("missing_key")
        error_type = classify_error(error)

        assert error_type == ErrorType.DATA_ERROR

    def test_classify_unknown_error(self):
        """Unknown errors should fall back to UNKNOWN"""
        error = Exception("Something weird happened")
        error_type = classify_error(error)

        assert error_type == ErrorType.UNKNOWN_ERROR


class TestFallbackStrategies:
    """Test fallback strategy functions"""

    def test_recover_ollama_error(self):
        """Ollama fallback should return user-friendly message"""
        result = recover_ollama_error(Exception("Service down"))

        assert "response" in result
        assert "unavailable" in result["response"].lower()
        assert result["model"] == "fallback"
        assert result["done"] is True

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    def test_recover_plot_generation_error(self, mock_close, mock_savefig):
        """Plot fallback should generate error plot"""
        from app.error_tracking import recover_plot_generation_error

        result = recover_plot_generation_error(Exception("Plot failed"))

        assert isinstance(result, bytes)
        mock_savefig.assert_called_once()
        mock_close.assert_called_once()


class TestMemoryManagement:
    """Test memory cleanup functionality"""

    def test_memory_cleanup_when_threshold_exceeded(self):
        """Memory cleanup should trigger when threshold exceeded"""
        recovery_manager = RecoveryManager()

        # This test requires actual memory pressure, so we mock it
        with patch('psutil.Process') as mock_process:
            mock_process.return_value.memory_info.return_value.rss = 400 * 1024 * 1024  # 400MB

            result = recovery_manager.handle_memory_error(threshold_mb=300)

            assert result is True
            assert recovery_manager.recovery_stats['memory_cleanups'] == 1

    def test_memory_cleanup_skipped_when_below_threshold(self):
        """Memory cleanup should skip when below threshold"""
        recovery_manager = RecoveryManager()

        with patch('psutil.Process') as mock_process:
            mock_process.return_value.memory_info.return_value.rss = 200 * 1024 * 1024  # 200MB

            result = recovery_manager.handle_memory_error(threshold_mb=300)

            assert result is False
            assert recovery_manager.recovery_stats['memory_cleanups'] == 0


class TestRecoveryStats:
    """Test recovery statistics tracking"""

    def test_recovery_stats_initial_state(self):
        """Stats should start at zero"""
        recovery_manager = RecoveryManager()
        stats = recovery_manager.get_recovery_stats()

        assert stats['total_retries'] == 0
        assert stats['successful_retries'] == 0
        assert stats['failed_retries'] == 0
        assert stats['circuit_breaker_blocks'] == 0
        assert stats['graceful_degradations'] == 0
        assert stats['retry_success_rate'] == 0.0

    def test_retry_success_rate_calculation(self):
        """Success rate should be calculated correctly"""
        recovery_manager = RecoveryManager()

        # Manually set stats
        recovery_manager.recovery_stats['total_retries'] = 10
        recovery_manager.recovery_stats['successful_retries'] = 8

        stats = recovery_manager.get_recovery_stats()

        assert stats['retry_success_rate'] == 0.8

    def test_circuit_breaker_states_in_stats(self):
        """Stats should include circuit breaker states"""
        recovery_manager = RecoveryManager()
        stats = recovery_manager.get_recovery_stats()

        assert 'circuit_breakers' in stats
        assert 'ollama' in stats['circuit_breakers']
        assert 'fastf1' in stats['circuit_breakers']
        assert 'modal' in stats['circuit_breakers']


class TestGlobalInstance:
    """Test global recovery manager singleton"""

    def test_get_recovery_manager_singleton(self):
        """get_recovery_manager should return singleton"""
        manager1 = get_recovery_manager()
        manager2 = get_recovery_manager()

        assert manager1 is manager2

    def test_get_recovery_manager_with_error_tracker(self):
        """Recovery manager should integrate with error tracker"""
        from app.error_tracking import get_error_tracker

        error_tracker = get_error_tracker()
        recovery_manager = get_recovery_manager(error_tracker)

        assert recovery_manager.error_tracker is error_tracker


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
