# ─────────────────────────────────────────────────────────────────────────────
# Incident Response Agent — Makefile
# Requires: Docker Compose v2 (docker compose), Python 3.11+
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: up down seed logs help

COMPOSE = docker compose
SERVICE_APP = app

## up: Build images and start all services in the background
up:
	$(COMPOSE) up --build -d
	@echo ""
	@echo "  Services ready:"
	@echo "    Order Service  →  http://localhost:8000"
	@echo "    Prometheus     →  http://localhost:9090"
	@echo "    Loki           →  http://localhost:3100"
	@echo "    Grafana        →  http://localhost:3000  (admin / admin)"
	@echo ""
	@echo "  Run 'make seed' to populate the database with sample orders."

## down: Stop and remove all containers, networks (volumes are preserved)
down:
	$(COMPOSE) down

## seed: Populate the database with sample orders
seed:
	@echo "Waiting for order-service to be ready..."
	$(COMPOSE) exec $(SERVICE_APP) python -c \
		"import time, httpx; [time.sleep(1) or print('.') for _ in range(15) if httpx.get('http://localhost:8000/health').status_code != 200]" \
		2>/dev/null || true
	$(COMPOSE) exec $(SERVICE_APP) python seed.py
	@echo "Seed complete."

## logs: Follow logs for all services (Ctrl-C to exit)
logs:
	$(COMPOSE) logs -f

## help: Show this help message
help:
	@grep -E '^##' Makefile | sed 's/^## //'
