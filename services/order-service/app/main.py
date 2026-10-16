"""
Order-service FastAPI application entry point.

Responsibilities:
  - Create DB tables on startup
  - Register metrics middleware (records latency, counts, errors)
  - Mount all routers
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app import metrics as m
from app.config import settings
from app.database import create_tables
from app.logging_config import logger
from app.routes import router
from datetime import datetime, timezone

# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Order Service",
    description="Simulated production order service for the Incident Response Agent.",
    version=settings.app_version,
)

# Publish version as a Prometheus info metric
m.APP_INFO.info({"version": settings.app_version})

DEPLOYMENTS = [
    {
        "id": 1,
        "version": "v1.8.1",
        "sha": "f6776ef9e132",
        "deployed_by": "release-pipeline",
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }
]

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup() -> None:
    create_tables()
    logger.info("Order service started", extra={"version": settings.app_version})


# ── Middleware: observability ─────────────────────────────────────────────────

@app.middleware("http")
async def observability_middleware(request: Request, call_next) -> Response:
    start = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    error_type: str | None = None
    status_code = 200

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:
        status_code = 500
        error_type = type(exc).__name__
        logger.error(
            "Unhandled exception",
            extra={
                "endpoint": endpoint,
                "method": method,
                "error_type": error_type,
                "status": status_code,
            },
            exc_info=True,
        )
        response = JSONResponse({"detail": "Internal server error"}, status_code=500)

    duration = time.perf_counter() - start
    duration_ms = round(duration * 1000, 2)

    # Prometheus
    m.REQUEST_COUNT.labels(
        method=method, endpoint=endpoint, status_code=str(status_code)
    ).inc()
    m.REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

    if status_code >= 400:
        err_label = error_type or ("client_error" if status_code < 500 else "server_error")
        m.ERROR_COUNT.labels(method=method, endpoint=endpoint, error_type=err_label).inc()

    # Structured log
    log_fn = logger.error if status_code >= 500 else logger.warning if status_code >= 400 else logger.info
    log_fn(
        "request",
        extra={
            "method": method,
            "endpoint": endpoint,
            "status": status_code,
            "duration_ms": duration_ms,
            **({"error_type": error_type} if error_type else {}),
        },
    )

    return response


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(router)
@app.get("/admin/deployments")
def get_deployments():
    return {
        "deployments": DEPLOYMENTS
    }

@app.post("/admin/deployment")
def create_deployment(payload: dict):
    version = payload.get("version", "unknown")
    deployed_by = payload.get(
        "deployed_by",
        "unknown",
    )

    sha_map = {
        "v1.8.1": "f6776ef9e132",
        "v1.8.2": "62f544cfe24f",
        "v1.8.3": "5089441bc586",
    }

    deployment = {
        "id": len(DEPLOYMENTS) + 1,
        "version": version,
        "sha": sha_map.get(version, "unknown"),
        "deployed_by": deployed_by,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }

    DEPLOYMENTS.append(deployment)

    return deployment