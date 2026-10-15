# Order Service

Simulated production service for the **Incident Response Agent** project.

## Architecture

```
app/
  __init__.py       package marker
  config.py         Settings (pydantic-settings) + runtime failure flags
  database.py       SQLAlchemy engine, SessionLocal, get_db dependency
  models.py         ORM models: customers, products, orders, order_items
  schemas.py        Pydantic v2 request/response schemas
  crud.py           DB query functions (normal path + N+1 path)
  failures.py       Failure injection side-effects
  metrics.py        Prometheus metric objects (singletons)
  logging_config.py JSON structured logger
  routes.py         FastAPI route handlers
  main.py           App factory + observability middleware
seed.py             Seed script (~1k customers, 5k orders, 20k items)
tests/
  test_orders.py    Pytest suite (uses SQLite, no Docker needed)
Dockerfile          Multi-stage build; accepts VERSION build arg
docker-compose.yml  App + Postgres
```

## Running

```bash
# Start services
docker compose up --build

# Seed data (once the app is healthy)
docker compose exec app python seed.py
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /metrics | Prometheus metrics |
| GET | /orders | Paginated order list (with customer + items) |
| GET | /orders/{id} | Single order |
| POST | /orders | Create an order |
| GET | /admin/failure | Current failure-injection status |
| POST | /admin/failure | Toggle failure modes at runtime |

## Failure Injection

Toggle via environment variables **or** the `POST /admin/failure` endpoint.

| Flag | Env var | Effect |
|------|---------|--------|
| N+1 queries | `N_PLUS_ONE=true` | Items loaded one-query-per-order |
| Slow DB | `DB_SLOW=true` / `DB_SLOW_SECONDS=3` | `pg_sleep()` before every query |
| High CPU | `HIGH_CPU=true` | Background thread burns a CPU core |
| Error spike | `ERROR_SPIKE=true` / `ERROR_SPIKE_RATE=0.5` | 50% of requests → 500 |
| Memory leak | `MEMORY_LEAK=true` | Grows an in-memory list by 1 KB/request |

Example – enable error spike at runtime:
```bash
curl -X POST http://localhost:8000/admin/failure \
  -H 'Content-Type: application/json' \
  -d '{"error_spike": true, "error_spike_rate": 0.8}'

# Reset all flags
curl -X POST http://localhost:8000/admin/failure \
  -H 'Content-Type: application/json' \
  -d '{"reset": true}'
```

## Prometheus Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `http_requests_total` | Counter | method, endpoint, status_code |
| `http_request_duration_seconds` | Histogram | method, endpoint |
| `http_errors_total` | Counter | method, endpoint, error_type |
| `db_queries_total` | Counter | endpoint, operation |
| `db_query_duration_seconds` | Histogram | endpoint, operation |
| `app_info` | Info | version |

## Tests

```bash
# Install deps in a venv
pip install -r requirements.txt

# Run (no Docker required – uses SQLite)
pytest
```

## Docker Build with VERSION

```bash
docker build --build-arg VERSION=1.2.3 -t order-service:1.2.3 .
```
