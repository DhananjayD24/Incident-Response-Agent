"""
FastAPI routers for the order-service.

Routes:
  GET  /health
  GET  /metrics          (Prometheus text format)
  GET  /orders
  GET  /orders/{id}
  POST /orders
  GET  /admin/failure    (current failure-injection status)
  POST /admin/failure    (toggle failure modes at runtime)
"""
from __future__ import annotations

import datetime
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from app import crud
from app.config import (
    clear_failure_flags,
    get_failure_flag,
    set_failure_flag,
    settings,
)
from app.database import get_db
from app.failures import maybe_error_spike, maybe_memory_leak, sync_cpu_burn_state
from app.logging_config import logger
from app.models import Deployment
from app.schemas import (
    DeploymentCreate,
    DeploymentOut,
    FailureConfig,
    FailureStatus,
    OrderCreate,
    OrderListOut,
    OrderOut,
)

router = APIRouter()



# ── /health ──────────────────────────────────────────────────────────────────

@router.get("/health", tags=["ops"])
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": settings.app_version,
        "db": "ok" if db_ok else "error",
    }


# ── /metrics ─────────────────────────────────────────────────────────────────

@router.get("/metrics", tags=["ops"], include_in_schema=False)
def metrics() -> Response:
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# ── /orders ───────────────────────────────────────────────────────────────────

@router.get("/orders", response_model=OrderListOut, tags=["orders"])
def list_orders(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> OrderListOut:
    _apply_common_failures(db)

    orders, total = crud.list_orders(db, endpoint="/orders", page=page, page_size=page_size)
    return OrderListOut(total=total, page=page, page_size=page_size, items=orders)


@router.get("/orders/{order_id}", response_model=OrderOut, tags=["orders"])
def get_order(
    order_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> OrderOut:
    _apply_common_failures(db)

    order = crud.get_order(db, order_id, endpoint="/orders/{id}")
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/orders", response_model=OrderOut, status_code=201, tags=["orders"])
def create_order(
    payload: OrderCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> OrderOut:
    _apply_common_failures(db)

    try:
        order = crud.create_order(db, payload, endpoint="/orders")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return order


# ── /admin/failure ────────────────────────────────────────────────────────────

@router.get("/admin/failure", response_model=FailureStatus, tags=["admin"])
def get_failure_status() -> FailureStatus:
    return FailureStatus(
        n_plus_one=bool(get_failure_flag("n_plus_one")),
        db_slow=bool(get_failure_flag("db_slow")),
        db_slow_seconds=float(get_failure_flag("db_slow_seconds")),
        high_cpu=bool(get_failure_flag("high_cpu")),
        error_spike=bool(get_failure_flag("error_spike")),
        error_spike_rate=float(get_failure_flag("error_spike_rate")),
        memory_leak=bool(get_failure_flag("memory_leak")),
    )


@router.post("/admin/failure", response_model=FailureStatus, tags=["admin"])
def set_failure_status(config: FailureConfig) -> FailureStatus:
    if config.reset:
        clear_failure_flags()
    else:
        _maybe_set("n_plus_one", config.n_plus_one)
        _maybe_set("db_slow", config.db_slow)
        _maybe_set("db_slow_seconds", config.db_slow_seconds)
        _maybe_set("high_cpu", config.high_cpu)
        _maybe_set("error_spike", config.error_spike)
        _maybe_set("error_spike_rate", config.error_spike_rate)
        _maybe_set("memory_leak", config.memory_leak)

    logger.info(
        "Failure flags updated",
        extra={
            "n_plus_one": get_failure_flag("n_plus_one"),
            "db_slow": get_failure_flag("db_slow"),
            "high_cpu": get_failure_flag("high_cpu"),
            "error_spike": get_failure_flag("error_spike"),
            "memory_leak": get_failure_flag("memory_leak"),
        },
    )
    return get_failure_status()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _maybe_set(name: str, value) -> None:
    if value is not None:
        set_failure_flag(name, value)


def _apply_common_failures(db) -> None:
    """Side-effects applied on every data-plane request."""
    sync_cpu_burn_state()
    maybe_memory_leak()
    spike_reason = maybe_error_spike()
    if spike_reason:
        raise HTTPException(status_code=500, detail=spike_reason)


# ── /deployments ──────────────────────────────────────────────────────────────

@router.get("/deployments", response_model=list[DeploymentOut], tags=["ops"])
def list_deployments(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[DeploymentOut]:
    """Return recent deployment records (newest first)."""
    from sqlalchemy import select as sa_select
    rows = db.scalars(
        sa_select(Deployment).order_by(Deployment.deployed_at.desc()).limit(limit)
    ).all()
    return list(rows)


@router.post("/deployments", response_model=DeploymentOut, status_code=201, tags=["ops"])
def record_deployment(
    payload: DeploymentCreate,
    db: Session = Depends(get_db),
) -> DeploymentOut:
    """Record a new deployment event in the audit log."""
    deploy = Deployment(
        service=payload.service,
        version=payload.version,
        commit_sha=payload.commit_sha,
        deployed_by=payload.deployed_by,
        notes=payload.notes,
    )
    db.add(deploy)
    db.commit()
    db.refresh(deploy)
    logger.info(
        "deployment_recorded",
        extra={
            "service": deploy.service,
            "version": deploy.version,
            "deployed_by": deploy.deployed_by,
        },
    )
    return deploy
