"""
Shared Prometheus metrics for all routes.
Prevents duplicate metric registration errors.
"""

from prometheus_client import Counter, Histogram

# Shared Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"]
)
