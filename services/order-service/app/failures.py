"""
Failure injection helpers.

Each helper reads the current flag value (env or runtime override) and
applies the side-effect if the flag is active.
"""
from __future__ import annotations

import random
import threading
import time
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_failure_flag

# ── MEMORY_LEAK accumulator ───────────────────────────────────────────────────
_leak_store: list[bytes] = []
_LEAK_CHUNK_SIZE = 1024  # 1 KB per request


def maybe_memory_leak() -> None:
    """Append a small byte chunk to the module-level list (never freed)."""
    if get_failure_flag("memory_leak"):
        _leak_store.append(b"x" * _LEAK_CHUNK_SIZE)


# ── ERROR_SPIKE ───────────────────────────────────────────────────────────────

def maybe_error_spike() -> Optional[str]:
    """Return an error message string if the spike should fire, else None."""
    if get_failure_flag("error_spike"):
        rate = float(get_failure_flag("error_spike_rate"))
        if random.random() < rate:
            return "injected_error_spike"
    return None


# ── DB_SLOW ───────────────────────────────────────────────────────────────────

def maybe_db_slow(db: Session) -> None:
    """Execute pg_sleep to simulate a slow database."""
    if get_failure_flag("db_slow"):
        seconds = float(get_failure_flag("db_slow_seconds"))
        db.execute(text(f"SELECT pg_sleep({seconds})"))


# ── HIGH_CPU ──────────────────────────────────────────────────────────────────

_cpu_thread: Optional[threading.Thread] = None
_cpu_stop_event = threading.Event()


def _burn_cpu() -> None:
    """Tight loop that saturates one CPU core until stopped."""
    while not _cpu_stop_event.is_set():
        _ = sum(i * i for i in range(10_000))


def start_cpu_burn() -> None:
    global _cpu_thread
    if _cpu_thread is None or not _cpu_thread.is_alive():
        _cpu_stop_event.clear()
        _cpu_thread = threading.Thread(target=_burn_cpu, daemon=True, name="cpu-burner")
        _cpu_thread.start()


def stop_cpu_burn() -> None:
    _cpu_stop_event.set()


def sync_cpu_burn_state() -> None:
    """Called on each request: start/stop the CPU burner thread based on the flag."""
    if get_failure_flag("high_cpu"):
        start_cpu_burn()
    else:
        stop_cpu_burn()
