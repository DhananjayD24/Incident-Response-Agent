# Incident Response Agent

An AI agent that investigates production incidents in a local simulated environment,
finds the root cause using real observability data, recommends a fix, asks for human
approval, executes a rollback, and verifies recovery.

## Stack

- **App layer** — Python 3.11, FastAPI, Postgres 16
- **Observability** — Prometheus, Grafana Loki + Promtail, Grafana 10
- **Agent layer** — LangGraph, LangChain, MCP (Python SDK)
- **RAG** — Qdrant / Chroma
- **Frontend** — React / Next.js + Tailwind
- **Infra** — Docker Compose

---

## Quick Start

### Prerequisites

- Docker ≥ 24 with **Docker Compose v2** (`docker compose` — not `docker-compose`)
- `make` (Git Bash / WSL / Linux / macOS)

### 1 — Start the full stack

```bash
# From the repo root:
make up
```

This builds the order-service image and starts all six containers in the background.

### 2 — Seed the database

```bash
make seed
```

Inserts a set of realistic sample orders into PostgreSQL.

### 3 — Watch logs

```bash
make logs          # all services
make logs          # or: docker compose logs -f app
```

### 4 — Tear down

```bash
make down          # stops containers, keeps volumes
docker compose down -v   # also removes volumes (full reset)
```

---

## Service Ports

| Service       | URL                              | Credentials      |
|---------------|----------------------------------|------------------|
| Order Service | <http://localhost:8000>          | —                |
| API Docs      | <http://localhost:8000/docs>     | —                |
| Prometheus    | <http://localhost:9090>          | —                |
| Loki          | <http://localhost:3100>          | —                |
| Grafana       | <http://localhost:3000>          | admin / admin    |

---

## Observability

### Prometheus

Scrapes `app:8000/metrics` **every 5 s**.
Metrics exposed by the order-service:

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests (method, endpoint, status_code) |
| `http_request_duration_seconds` | Histogram | Request latency |
| `http_errors_total` | Counter | HTTP errors (method, endpoint, error_type) |
| `db_queries_total` | Counter | DB queries per endpoint/operation |
| `db_query_duration_seconds` | Histogram | DB query latency |
| `process_cpu_seconds_total` | Counter | CPU usage |
| `process_resident_memory_bytes` | Gauge | RSS memory |

### Grafana — pre-loaded dashboard

Open <http://localhost:3000> → **Dashboards → Order Service — SLO & Resources**.

Panels:

| Panel | Query |
|-------|-------|
| HTTP Latency p95 / p50 | `histogram_quantile(0.95, ...)` |
| HTTP Error Rate | `rate(http_errors_total[1m])` |
| DB Queries per Request | `rate(db_queries_total) / rate(http_requests_total)` |
| DB Query Latency p95 | `histogram_quantile(0.95, db_query_duration_seconds_bucket)` |
| CPU Usage | `rate(process_cpu_seconds_total[1m])` |
| Memory Usage | `process_resident_memory_bytes` |
| Order-Service Logs | Loki — `{service="app"}` |

### Loki + Promtail

Promtail uses Docker service-discovery to tail all container stdout/stderr and ships
structured JSON logs to Loki.  Query logs in Grafana Explore with
`{container="ira-order-service"}`.

---

## Failure Injection

Toggle failure modes at runtime without restarting:

```bash
# Trigger an error spike (30 % of requests → 500)
curl -X POST http://localhost:8000/admin/failure \
  -H 'Content-Type: application/json' \
  -d '{"error_spike": true, "error_spike_rate": 0.3}'

# Reset all flags
curl -X POST http://localhost:8000/admin/failure \
  -H 'Content-Type: application/json' \
  -d '{"reset": true}'
```

Available flags: `n_plus_one`, `db_slow`, `db_slow_seconds`, `high_cpu`,
`error_spike`, `error_spike_rate`, `memory_leak`.

---

## Repository Structure

| Directory | Purpose |
|-----------|---------|
| `services/order-service` | Simulated production service (FastAPI + Postgres) |
| `monitoring/prometheus` | Prometheus scrape config |
| `monitoring/promtail` | Promtail Docker-SD config |
| `monitoring/grafana` | Grafana provisioning (datasources + dashboard) |
| `mcp_server` | MCP server exposing observability tools to the agent |
| `agent` | LangGraph-based incident-response agent |
| `rag` | RAG pipeline (runbooks / post-mortems) |
| `eval` | Evaluation harness |
| `dashboard` | React/Next.js frontend |
| `docs` | Architecture docs |
