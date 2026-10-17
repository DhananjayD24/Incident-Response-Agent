import os


PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://prometheus:9090",
).rstrip("/")


LOKI_URL = os.getenv(
    "LOKI_URL",
    "http://loki:3100",
).rstrip("/")


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/incident_db",
)


GIT_REPO_PATH = os.getenv(
    "GIT_REPO_PATH",
    "/repo",
)


AUDIT_LOG_PATH = os.getenv(
    "AUDIT_LOG_PATH",
    "/app/logs/audit.jsonl",
)