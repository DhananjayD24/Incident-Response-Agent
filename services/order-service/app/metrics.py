"""
Prometheus metrics registry for the order-service.

Metrics:
  - http_requests_total          (counter, labels: method, endpoint, status_code)
  - http_request_duration_seconds (histogram, labels: method, endpoint)
  - http_errors_total            (counter, labels: method, endpoint, error_type)
  - db_queries_total             (counter, labels: endpoint, operation)
  - db_query_duration_seconds    (histogram, labels: endpoint, operation)
  - app_info                     (info, labels: version)
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram, Info

# ── HTTP ─────────────────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

ERROR_COUNT = Counter(
    "http_errors_total",
    "Total HTTP errors",
    ["method", "endpoint", "error_type"],
)

# ── Database ─────────────────────────────────────────────────────────────────

DB_QUERY_COUNT = Counter(
    "db_queries_total",
    "Total database queries",
    ["endpoint", "operation"],
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["endpoint", "operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# ── App info ─────────────────────────────────────────────────────────────────

APP_INFO = Info("app", "Application metadata")
