# Error Tracking Quick Start Guide

## Quick Reference

### Check System Health

```bash
# Development (port 5050)
curl http://localhost:5050/monitoring/health

# Production (port 5151)
curl http://localhost:5151/monitoring/health
```

### View Error Statistics

```bash
curl http://localhost:5050/monitoring/errors | jq
```

### View Recent Errors

```bash
curl http://localhost:5050/monitoring/errors/recent?limit=20 | jq
```

### View Specific Error Group

```bash
# Get fingerprint from error stats, then:
curl http://localhost:5050/monitoring/errors/group/FINGERPRINT | jq
```

### Clear Error History (Testing)

```bash
curl -X POST http://localhost:5050/monitoring/errors/clear
```

## Monitoring in Code

### Capture an Exception

```python
from app.error_tracking.error_tracker import get_error_tracker, ErrorSeverity

error_tracker = get_error_tracker()

try:
    risky_operation()
except Exception as e:
    error_tracker.capture_exception(
        e,
        context={'user': 'ABC123', 'action': 'plot_generation'},
        level=ErrorSeverity.ERROR
    )
    raise  # Re-raise if you want the error to propagate
```

### Capture a Warning Message

```python
error_tracker.capture_message(
    "Slow query detected: 5.2 seconds",
    level=ErrorSeverity.WARNING,
    context={'query': 'get_session', 'duration': 5.2}
)
```

### Get Error Statistics

```python
tracker = get_error_tracker()
stats = tracker.get_error_stats()

print(f"Total errors: {stats['total_errors']}")
print(f"Top errors: {stats['top_errors']}")
```

## Error Severity Levels

- **`ErrorSeverity.DEBUG`** - Debugging information
- **`ErrorSeverity.INFO`** - Informational messages
- **`ErrorSeverity.WARNING`** - Warnings (system continues)
- **`ErrorSeverity.ERROR`** - Errors (operation failed)
- **`ErrorSeverity.FATAL`** - Fatal errors (triggers immediate alert)

## Automatic Error Tracking

Error tracking is **automatic** for:

- ✅ All unhandled exceptions (app-wide)
- ✅ HTTP 5xx errors
- ✅ FastF1 session loading failures
- ✅ Ollama connection errors
- ✅ Plot generation failures
- ✅ Driver data loading errors
- ✅ Telemetry comparison errors

## Request Tracking

Every request gets:
- Unique request ID (in `X-Request-ID` header)
- Automatic performance timing
- Slow request warnings (>5 seconds)

## Error Dashboard

Access the visual error dashboard at:

```
http://localhost:5050/errors/dashboard
```

Features:
- Error rate visualization
- Top error groups
- Recent error timeline
- Error trends over time

## Common Patterns

### Pattern 1: Wrap Risky Operations

```python
try:
    result = external_api_call()
except RequestException as e:
    error_tracker.capture_exception(e, context={'api': 'external'})
    # Fallback logic
    result = use_cached_data()
```

### Pattern 2: Track Expected Errors Differently

```python
try:
    session = load_session(year, race)
except SessionNotAvailableError as e:
    # Don't track as error - this is expected behavior
    logging.warning(f"Session not available: {race}")
    return None
except Exception as e:
    # Unexpected error - track it
    error_tracker.capture_exception(e, level=ErrorSeverity.ERROR)
    raise
```

### Pattern 3: Add Rich Context

```python
error_tracker.capture_exception(
    exception,
    context={
        'operation': 'telemetry_comparison',
        'year': 2024,
        'race': 'Monaco Grand Prix',
        'drivers': ['VER', 'HAM'],
        'session_id': session_id,
        'cache_status': 'miss',
        'user_action': 'plot_generation'
    }
)
```

## Integration Points

### In Route Handlers

```python
@app.route('/api/data')
def get_data():
    try:
        data = fetch_data()
        return jsonify(data)
    except Exception as e:
        error_tracker.capture_exception(
            e,
            context={'endpoint': '/api/data'},
            level=ErrorSeverity.ERROR
        )
        return jsonify({'error': 'Failed to fetch data'}), 500
```

### In Background Tasks

```python
def background_preload():
    try:
        preload_sessions()
    except Exception as e:
        error_tracker.capture_exception(
            e,
            context={'task': 'background_preload'},
            level=ErrorSeverity.WARNING
        )
```

### In Service Layer

```python
class TelemetryService:
    def __init__(self):
        self.error_tracker = get_error_tracker()

    def process(self, data):
        try:
            return self._process_internal(data)
        except Exception as e:
            self.error_tracker.capture_exception(
                e,
                context={'service': 'telemetry', 'data_size': len(data)}
            )
            raise
```

## Configuration

Edit `app/__init__.py` to adjust error tracking:

```python
error_tracker = get_error_tracker({
    'max_queue_size': 1000,        # Max errors in memory
    'rate_limit_window': 60,       # Seconds
    'max_errors_per_window': 10    # Per fingerprint
})
```

## Troubleshooting

### No errors showing up?

1. Check if error tracker is initialized:
   ```python
   from app.error_tracking.error_tracker import get_error_tracker
   tracker = get_error_tracker()
   print(f"Queue size: {len(tracker.error_queue)}")
   ```

2. Verify middleware is registered:
   - Look for "Error tracking middleware registered" in logs

3. Check error suppression:
   ```python
   stats = tracker.get_error_stats()
   print(f"Suppressed: {stats['suppressed_errors']}")
   ```

### Too many duplicate errors?

Adjust rate limiting:
```python
error_tracker = get_error_tracker({
    'max_errors_per_window': 5  # Stricter rate limiting
})
```

### Memory usage high?

Reduce queue size:
```python
error_tracker = get_error_tracker({
    'max_queue_size': 500  # Smaller queue
})
```

Or clear errors periodically:
```python
tracker.clear_errors()
```

## Production Checklist

- [ ] Error tracking endpoints secured (add authentication)
- [ ] External alerting configured (Slack/PagerDuty)
- [ ] Error dashboard monitored regularly
- [ ] Rate limits tuned for production traffic
- [ ] Queue size appropriate for memory budget
- [ ] Error retention policy defined
- [ ] Sensitive data scrubbing enabled (if needed)

## Next Steps

1. **Set up external alerting** - Integrate with your monitoring system
2. **Create dashboards** - Grafana/Prometheus visualization
3. **Define SLOs** - Error rate targets and alerts
4. **Review errors weekly** - Fix recurring issues
5. **Tune configuration** - Adjust based on production metrics

## Support

For issues or questions about error tracking:

1. Check logs for error tracking initialization
2. Verify middleware is registered
3. Test with a manual error capture
4. Review error statistics endpoint
5. Check the integration summary document

---

**Remember:** Error tracking is automatic! You only need to add manual tracking for special cases or to provide additional context.
