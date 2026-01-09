# Error Tracking & Recovery System

Production-ready error tracking and recovery infrastructure for the F1 Telemetry application.

## Overview

The error tracking system provides three key capabilities:

1. **Error Tracking** (`error_tracker.py`): Capture, group, and monitor errors
2. **Structured Logging** (`structured_logger.py`): Context-rich logging with audit trails
3. **Error Recovery** (`recovery_manager.py`): Intelligent recovery with circuit breakers

## Quick Start

### Error Tracking

```python
from app.error_tracking import get_error_tracker, ErrorSeverity

tracker = get_error_tracker()

try:
    risky_operation()
except Exception as e:
    tracker.capture_exception(
        e,
        context={'user_id': 123, 'operation': 'plot_generation'},
        level=ErrorSeverity.ERROR
    )
```

### Error Recovery

```python
from app.error_tracking import get_recovery_manager, ErrorType

recovery_manager = get_recovery_manager()

result = recovery_manager.execute_with_recovery(
    func=call_external_service,
    service_name='ollama',
    error_type=ErrorType.API_ERROR,
    fallback=lambda: "Service unavailable",
    context={'request_id': request.id}
)
```

### Structured Logging

```python
from app.error_tracking import get_logger

logger = get_logger(__name__)

logger.info("Processing request", driver="VER", session="Q")
logger.error("Analysis failed", error=str(e), attempt=3)
```

## Components

### 1. Error Tracker

**Purpose**: Intelligent error grouping and monitoring

**Features**:
- Automatic error fingerprinting
- Duplicate suppression (rate limiting)
- Error grouping by similarity
- Top error identification
- Alert triggers

**Usage**:
```python
tracker = get_error_tracker()
fingerprint = tracker.capture_exception(error, context={'key': 'value'})
stats = tracker.get_error_stats()
```

### 2. Recovery Manager

**Purpose**: Intelligent error recovery strategies

**Features**:
- Circuit breaker pattern (CLOSED → OPEN → HALF_OPEN)
- Exponential backoff with jitter
- Service-specific retry policies
- Graceful degradation
- Memory management

**Services Protected**:
- `ollama`: AI inference (3 failures → 30s timeout)
- `fastf1`: F1 data API (5 failures → 60s timeout)
- `modal`: GPU function (3 failures → 45s timeout)

**Usage**:
```python
recovery_manager = get_recovery_manager()

# Execute with recovery
result = recovery_manager.execute_with_recovery(
    func=operation,
    service_name='fastf1',
    error_type=ErrorType.NETWORK_ERROR,
    fallback=fallback_function
)

# Or use decorator
@with_recovery('ollama', ErrorType.API_ERROR)
def call_ollama():
    # Your code here
    pass
```

### 3. Structured Logger

**Purpose**: Context-rich logging with audit trails

**Features**:
- Automatic context binding
- JSON and human-readable formats
- Audit logging for critical actions
- Request context tracking
- Flask integration

**Usage**:
```python
logger = get_logger(__name__)
logger = logger.bind(user_id=123, session="Q")
logger.info("Event occurred", additional="context")
logger.audit(AuditAction.CACHE_CLEAR, resource="sessions")
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Error Tracking System                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ErrorTracker          RecoveryManager      StructuredLogger │
│       │                      │                      │         │
│       │                      │                      │         │
│  ┌────▼────┐          ┌─────▼─────┐         ┌─────▼────┐   │
│  │ Error   │          │ Circuit   │         │ JSON     │   │
│  │ Groups  │          │ Breakers  │         │ Output   │   │
│  └─────────┘          └───────────┘         └──────────┘   │
│       │                      │                      │         │
│  ┌────▼────┐          ┌─────▼─────┐         ┌─────▼────┐   │
│  │ Rate    │          │ Retry     │         │ Audit    │   │
│  │ Limiting│          │ Policies  │         │ Trail    │   │
│  └─────────┘          └───────────┘         └──────────┘   │
│       │                      │                      │         │
│       └──────────────────────┴──────────────────────┘       │
│                              │                                │
│                        ┌─────▼─────┐                        │
│                        │ Monitoring│                        │
│                        │  & Alerts │                        │
│                        └───────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Recovery Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/recovery_stats` | GET | Get comprehensive recovery statistics |
| `/circuit_breakers` | GET | Get circuit breaker states |
| `/reset_circuit_breaker/<service>` | POST | Reset specific circuit breaker |
| `/reset_all_circuit_breakers` | POST | Reset all circuit breakers |
| `/trigger_memory_cleanup` | POST | Manually trigger memory cleanup |

### Error Monitoring

See `error_tracker.py` for error tracking endpoints.

## Configuration

### Circuit Breaker Tuning

```python
recovery_manager = get_recovery_manager()

# Adjust thresholds
recovery_manager.circuit_breakers['ollama'].config.failure_threshold = 5
recovery_manager.circuit_breakers['ollama'].config.timeout = 45.0
```

### Retry Policy Tuning

```python
# More aggressive network retries
recovery_manager.retry_policies[ErrorType.NETWORK_ERROR].max_attempts = 7
recovery_manager.retry_policies[ErrorType.NETWORK_ERROR].max_delay = 60.0
```

### Memory Management

```python
# Adjust memory threshold
recovery_manager.handle_memory_error(threshold_mb=400)
```

## Integration Examples

### Ollama API

```python
from app.error_tracking import get_recovery_manager, ErrorType, recover_ollama_error

def call_ollama_with_recovery(prompt: str):
    recovery_manager = get_recovery_manager()

    def call():
        return requests.post(ollama_url, json={'prompt': prompt})

    return recovery_manager.execute_with_recovery(
        func=call,
        service_name='ollama',
        error_type=ErrorType.API_ERROR,
        fallback=lambda ctx: recover_ollama_error(None, ctx)
    )
```

### FastF1 Session Loading

```python
from app.error_tracking import get_recovery_manager, ErrorType, recover_fastf1_error

def load_session_with_recovery(year, race, session_type):
    recovery_manager = get_recovery_manager()

    def load():
        return session_manager._load_session_internal(year, race, session_type)

    def fallback(ctx):
        return recover_fastf1_error(None, context={
            'session_manager': session_manager,
            'cache_key': (year, race, session_type)
        })

    return recovery_manager.execute_with_recovery(
        func=load,
        service_name='fastf1',
        error_type=ErrorType.NETWORK_ERROR,
        fallback=fallback
    )
```

### Plot Generation

```python
from app.error_tracking import get_recovery_manager, recover_plot_generation_error

def generate_plot_with_recovery(session, driver1, driver2):
    recovery_manager = get_recovery_manager()

    # Check memory
    recovery_manager.handle_memory_error(threshold_mb=300)

    try:
        return compare_fastest_laps(session, driver1, driver2)
    except Exception as e:
        return recover_plot_generation_error(e)
    finally:
        recovery_manager.handle_memory_error(threshold_mb=300)
```

## Monitoring

### Health Check

```python
def check_system_health():
    recovery_manager = get_recovery_manager()
    error_tracker = get_error_tracker()

    health = {
        'status': 'healthy',
        'issues': [],
        'recovery_stats': recovery_manager.get_recovery_stats(),
        'error_stats': error_tracker.get_error_stats()
    }

    # Check for issues
    for name, cb_state in health['recovery_stats']['circuit_breakers'].items():
        if cb_state['state'] == 'open':
            health['status'] = 'degraded'
            health['issues'].append(f"Circuit breaker OPEN: {name}")

    return health
```

### Prometheus Metrics

```python
from prometheus_client import Counter, Gauge

CIRCUIT_BREAKER_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['service']
)

RECOVERY_RETRIES = Counter(
    'recovery_retries_total',
    'Total retry attempts',
    ['service', 'result']
)
```

## Testing

### Unit Tests

```bash
# Run recovery manager tests
uv run pytest tests/test_recovery_manager.py -v

# Run specific test
uv run pytest tests/test_recovery_manager.py::TestCircuitBreaker::test_circuit_breaker_opens_after_threshold -v
```

### Integration Tests

See `examples/recovery_integration_examples.py` for complete examples.

### Manual Testing

```bash
# Check recovery stats
curl http://localhost:5050/recovery_stats

# Check circuit breaker states
curl http://localhost:5050/circuit_breakers

# Trigger memory cleanup
curl -X POST http://localhost:5050/trigger_memory_cleanup

# Reset circuit breaker
curl -X POST http://localhost:5050/reset_circuit_breaker/ollama
```

## Troubleshooting

### Circuit Breaker Keeps Opening

**Cause**: Service is actually down or network issues

**Fix**:
1. Check service health (Ollama, FastF1 API)
2. Review error logs: `tail -f logs/app.log | grep "Circuit breaker"`
3. Adjust thresholds if too sensitive
4. Reset manually: `POST /reset_circuit_breaker/ollama`

### High Retry Count

**Cause**: Aggressive retry policies or frequent failures

**Fix**:
1. Review retry stats: `GET /recovery_stats`
2. Tune retry policies (reduce max attempts)
3. Investigate root cause of failures
4. Add better fallback strategies

### Memory Issues

**Cause**: Plot generation or data caching

**Fix**:
1. Trigger cleanup: `POST /trigger_memory_cleanup`
2. Lower memory threshold
3. Reduce cache size in SessionManager
4. Check for matplotlib figure leaks

## Performance Impact

- Circuit breaker check: ~0.1ms per call
- Retry logic: 0ms (only on failures)
- Memory monitoring: ~1ms per check
- Error tracking: ~0.5ms per error

**Total overhead**: < 1ms in happy path

## Documentation

- **Detailed Guide**: See `docs/ERROR_RECOVERY_GUIDE.md`
- **Integration Guide**: See `docs/RECOVERY_INTEGRATION.md`
- **Examples**: See `examples/recovery_integration_examples.py`
- **Tests**: See `tests/test_recovery_manager.py`

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review recovery stats: `GET /recovery_stats`
3. Check logs: `tail -f logs/app.log`
4. Open GitHub issue with stats output
