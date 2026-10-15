"""
Order Service – application settings loaded from environment variables.
All failure-injection flags live here so they can be toggled at runtime
via environment variables or the POST /admin/failure endpoint.
"""
from __future__ import annotations

import threading
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql://orders:orders@db:5432/orders",
        alias="DATABASE_URL",
    )

    # ── App meta ────────────────────────────────────────────────────────────
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ── Failure injection flags ─────────────────────────────────────────────
    # N+1: load order items one-query-per-order instead of a join
    n_plus_one: bool = Field(default=False, alias="N_PLUS_ONE")

    # DB_SLOW: prepend pg_sleep(db_slow_seconds) to every DB operation
    db_slow: bool = Field(default=False, alias="DB_SLOW")
    db_slow_seconds: float = Field(default=2.0, alias="DB_SLOW_SECONDS")

    # HIGH_CPU: spin a background thread that burns CPU
    high_cpu: bool = Field(default=False, alias="HIGH_CPU")

    # ERROR_SPIKE: return HTTP 500 with this probability (0.0–1.0)
    error_spike: bool = Field(default=False, alias="ERROR_SPIKE")
    error_spike_rate: float = Field(default=0.3, alias="ERROR_SPIKE_RATE")

    # MEMORY_LEAK: append a 1 KB chunk to a module-level list on every request
    memory_leak: bool = Field(default=False, alias="MEMORY_LEAK")


# Singleton – imported everywhere
settings = Settings()

# ── Runtime-mutable failure state (POST /admin/failure mutates this dict) ─
_failure_lock = threading.Lock()
_runtime_failures: dict[str, object] = {}


def get_failure_flag(name: str) -> object:
    """Return the runtime override if set, else fall back to settings."""
    with _failure_lock:
        if name in _runtime_failures:
            return _runtime_failures[name]
    return getattr(settings, name)


def set_failure_flag(name: str, value: object) -> None:
    with _failure_lock:
        _runtime_failures[name] = value


def clear_failure_flags() -> None:
    with _failure_lock:
        _runtime_failures.clear()
