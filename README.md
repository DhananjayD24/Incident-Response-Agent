# Incident Response Agent

An AI agent that investigates production incidents in a local simulated environment,
finds the root cause using real observability data, recommends a fix, asks for human
approval, executes a rollback, and verifies recovery.

## Stack
- Python 3.11, FastAPI, Postgres, Prometheus, Loki + Promtail, Grafana
- Docker Compose, MCP (Python SDK), LangGraph, LangChain
- Qdrant (or Chroma), React/Next.js + Tailwind

## Structure

| Directory | Purpose |
|-----------|---------|
| `services/order-service` | Simulated production service (FastAPI + Postgres) |
| `mcp_server` | MCP server exposing observability tools to the agent |
| `agent` | LangGraph-based incident-response agent |
| `rag` | RAG pipeline (runbooks / post-mortems) |
| `eval` | Evaluation harness |
| `dashboard` | React/Next.js frontend |
| `docs` | Architecture docs |

## Quick Start

### Order Service

```bash
cd services/order-service
docker compose up --build
# Seed data
docker compose exec app python seed.py
```

See `services/order-service/README.md` for full details.
