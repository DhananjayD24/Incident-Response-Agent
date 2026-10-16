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
| Locust UI     | <http://localhost:8089>          | — (profile `traffic`) |

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

Prefer the scenario CLI (below) over raw curl — it composes the flags,
records deployment events, and prints what to watch in Grafana.

---

## Traffic Generator

`services/traffic` runs Locust with a weighted, realistic traffic mix
(40 % `GET /orders`, 35 % `GET /orders/{id}`, 20 % `POST /orders`, 5 % `/health`).

```bash
make traffic          # builds + starts the traffic container (profile: traffic)
docker compose --profile traffic up -d traffic   # same, without make
```

The container runs **headless by default** (steady traffic immediately).
Set `LOCUST_HEADLESS=false` to get the Locust web UI on
<http://localhost:8089> and start/stop traffic manually.

Run Locust locally instead of Docker:

```bash
pip install -r services/traffic/requirements.txt
locust -f services/traffic/locustfile.py --headless -u 10 -r 2 --host http://localhost:8000
```

---

## Scenarios

`scripts/scenarios.py` drives incident scenarios end-to-end:

```bash
python scripts/scenarios.py list                 # show available scenarios
python scripts/scenarios.py start bad_deploy     # trigger a scenario
python scripts/scenarios.py status               # health + active flags + recent deploys
python scripts/scenarios.py reset                # back to healthy state
```

| Scenario | What happens | True root cause |
|----------|--------------|-----------------|
| `n_plus_one` | DB queries/request explodes (N+1 anti-pattern) | `n_plus_one` flag |
| `db_slow` | 2 s `pg_sleep` before every query | `db_slow` flag |
| `high_cpu` | CPU burn thread + 30 % errors | **`error_spike`** — CPU is the symptom |
| `error_spike` | 30 % of requests return 500 | `error_spike` flag |
| `memory_leak` | 1 KB/request accumulated in RSS | `memory_leak` flag |
| `bad_deploy` | Deploys `order-service:v1.8.2` (N+1 bug) over `v1.8.1` and records both in the `deployments` table | regression in `v1.8.2` |
| `red_herring_1` | Harmless `v1.8.3` deploy **at the same moment** a DB slowdown starts | **`db_slow`** — the deploy is innocent |
| `red_herring_2` | CPU spike driven by a 50 % error retry loop | **`error_spike`** — CPU is the symptom |

Deployment events are recorded in the `deployments` table
(`service, version, timestamp, commit_sha, deployed_by`) via
`POST /deployments` and readable via `GET /deployments`.

---

## Ground Truth & Evaluation

Every scenario has a ground-truth file in `eval/ground_truth/<scenario>.json`
with the scenario name, the **true root cause**, the **key evidence signals**
(metrics, expected direction, thresholds), red herrings, the recommended fix,
and machine-checkable `evaluation_checks` used by the eval harness.

```bash
python -m pytest eval/tests          # schema + scenario↔ground-truth coverage
```

---

## Tests

```bash
python -m pytest                                # in services/order-service (API + failure injection)
python -m pytest eval/tests services/traffic/tests   # from repo root (ground truth + traffic gen)
```

---

## Repository Structure

| Directory | Purpose |
|-----------|---------|
| `services/order-service` | Simulated production service (FastAPI + Postgres) |
| `services/traffic` | Locust traffic generator |
| `scripts/scenarios.py` | CLI to start/reset incident scenarios |
| `monitoring/prometheus` | Prometheus scrape config |
| `monitoring/promtail` | Promtail Docker-SD config |
| `monitoring/grafana` | Grafana provisioning (datasources + dashboard) |
| `mcp_server` | MCP server exposing observability tools to the agent |
| `agent` | LangGraph-based incident-response agent |
| `rag` | RAG pipeline (runbooks / post-mortems) |
| `eval` | Evaluation harness + `ground_truth/` scenario labels |
| `dashboard` | React/Next.js frontend |
| `docs` | Architecture docs |
