#!/usr/bin/env python3
"""
Incident Response Agent — Scenario CLI
=======================================
Usage
-----
  python scripts/scenarios.py start <scenario_name>
  python scripts/scenarios.py reset
  python scripts/scenarios.py list
  python scripts/scenarios.py status

Scenarios
---------
  n_plus_one      Classic N+1 query bug — high DB-query-per-request count
  db_slow         Slow-query injection — p95 latency spikes, low error rate
  high_cpu        CPU spin loop (error-loop root cause, CPU is the symptom)
  error_spike     Random 500 errors at 30 % rate
  memory_leak     RSS grows continuously
  bad_deploy      Deploy order-service:v1.8.2 (N+1 bug), record in deployments
  red_herring_1   Harmless deploy (v1.8.3 text change) + db_slow at same time
  red_herring_2   CPU spike caused by an error retry loop (cause: error_spike)

Reset
-----
  python scripts/scenarios.py reset   # POST /admin/failure {reset: true}

Each scenario is self-contained, idempotent, and leaves the system in a
stable (if degraded) state until you call reset.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# Windows consoles default to cp1252, which cannot encode ✓/─/→.
# Never crash on output — replace unencodable chars (use `chcp 65001` for pretty output).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"
TIMEOUT = 10.0

# Release commit SHAs — must match the tags in services/order-service-repo
# (verify with: git -C services/order-service-repo rev-parse 'v1.8.1^{commit}')
VERSIONS: dict[str, dict[str, str]] = {
    "v1.8.0": {
        "commit_sha": "86e5da365eaf2fe079cb156656c3cbc05a182ce9",
        "notes": "Baseline — orders API (list, lookup, create)",
    },
    "v1.8.1": {
        "commit_sha": "f6776ef9e132a09b514a76548433084e5f20e27d",
        "notes": "Stable release — efficient JOIN queries",
    },
    "v1.8.2": {
        "commit_sha": "62f544cfe24fd8ecb228f664454373ba5d535d50",
        "notes": "BUG: N+1 query regression in order listing endpoint",
    },
    "v1.8.3": {
        "commit_sha": "5089441bc5861f91159809d2996de816a31d97f2",
        "notes": "Text change in /health response (cosmetic, harmless)",
    },
}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    try:
        resp = httpx.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        _die(f"HTTP {exc.response.status_code} from {url}: {exc.response.text}")
    except httpx.RequestError as exc:
        _die(f"Could not connect to {url}: {exc}\n  Is the stack running?  Run: make up")


def _get(path: str) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    try:
        resp = httpx.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        _die(f"HTTP {exc.response.status_code} from {url}: {exc.response.text}")
    except httpx.RequestError as exc:
        _die(f"Could not connect to {url}: {exc}\n  Is the stack running?  Run: make up")


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _info(msg: str) -> None:
    print(f"  → {msg}")


# ── Deployment recorder ───────────────────────────────────────────────────────

def _record_deployment(version: str, deployed_by: str = "scenarios-cli") -> None:
    """POST to /deployments to record a deploy event in the audit table."""
    meta = VERSIONS.get(version, {})
    payload = {
        "service": "order-service",
        "version": version,
        "commit_sha": meta.get("commit_sha"),
        "deployed_by": deployed_by,
        "notes": meta.get("notes"),
    }
    result = _post("/deployments", payload)
    _ok(
        f"Deployment recorded — order-service@{version} "
        f"(id={result.get('id')}, sha={meta.get('commit_sha', '')[:8]}…)"
    )


# ── Failure-injection helpers ─────────────────────────────────────────────────

def _set_failure(**kwargs: Any) -> dict[str, Any]:
    return _post("/admin/failure", kwargs)


def _reset_failure() -> dict[str, Any]:
    return _post("/admin/failure", {"reset": True})


# ── Individual scenario functions ─────────────────────────────────────────────

def scenario_n_plus_one() -> None:
    """
    N+1 query bug: each GET /orders fires one extra DB query per order row.
    Root cause: n_plus_one flag active (simulates a missing eager-load in code).
    Signals:  db_queries_total per request jumps from ~2 to ~22 (for page_size=20)
              db_query_duration_seconds p95 rises moderately
              http_request_duration_seconds p95 rises
    """
    _info("Activating N+1 query mode…")
    _set_failure(n_plus_one=True)
    _record_deployment("v1.8.2", deployed_by="scenarios-cli[bad_deploy]")
    _ok("N+1 query bug is now ACTIVE. Watch 'DB Queries per Request' in Grafana spike.")


def scenario_db_slow() -> None:
    """
    Slow database queries: pg_sleep(2) injected before every DB operation.
    Root cause: db_slow flag (simulates a missing index or lock contention).
    Signals:  http_request_duration_seconds p95 → 2–3 s
              db_query_duration_seconds p95 → 2+ s
              http_requests_total rate drops (throughput limited by latency)
    """
    _info("Injecting DB slow-query (2 s sleep per query)…")
    _set_failure(db_slow=True, db_slow_seconds=2.0)
    _ok("DB slow mode ACTIVE. Watch latency panels spike in Grafana.")


def scenario_high_cpu() -> None:
    """
    High CPU via error retry loop:
    - error_spike causes 30 % of requests to return 500
    - high_cpu spins a background thread (models the CPU load caused by retries)
    Root cause: error_spike (the CPU spike is a *symptom*, not the cause)
    Red herring: CPU is elevated — naive diagnosis blames the CPU first.
    Signals:  http_errors_total rate rises
              process_cpu_seconds_total rises
              http_request_duration_seconds unaffected (errors are fast)
    """
    _info("Starting error spike (30 %) + CPU burn (symptom of retry loop)…")
    _set_failure(error_spike=True, error_spike_rate=0.3, high_cpu=True)
    _ok("High-CPU (error-loop) scenario ACTIVE.")
    _info("NOTE: CPU is the *symptom* — true root cause is error_spike.")


def scenario_error_spike() -> None:
    """
    Pure random 500 error rate (no CPU side-effect).
    Root cause: error_spike flag.
    Signals:  http_errors_total rate spikes sharply
              http_request_duration_seconds p95 unchanged (errors are fast)
    """
    _info("Injecting error spike at 30 % rate…")
    _set_failure(error_spike=True, error_spike_rate=0.3)
    _ok("Error spike ACTIVE. Watch 'HTTP Error Rate' panel in Grafana.")


def scenario_memory_leak() -> None:
    """
    Memory leak: 1 KB appended to a module-level list on every request.
    Root cause: memory_leak flag.
    Signals:  process_resident_memory_bytes climbs steadily
              No latency or error-rate increase (early stage)
    """
    _info("Activating memory leak (1 KB/request accumulated)…")
    _set_failure(memory_leak=True)
    _ok("Memory leak ACTIVE. Watch 'Memory Usage' panel grow in Grafana.")


def scenario_bad_deploy() -> None:
    """
    Bad deployment of order-service:v1.8.2 (contains the N+1 bug).
    - Records v1.8.1 (stable) and then v1.8.2 (buggy) in the deployments table.
    - Activates the N+1 failure flag to simulate the regression.
    Root cause: regression introduced in v1.8.2 (missing eager-load).
    Signals:  deployment event at T=0 (deployments table)
              db_queries_total / http_requests_total ratio jumps immediately after
              http_request_duration_seconds p95 rises gradually
    """
    _info("Simulating deployment of order-service:v1.8.1 (stable baseline)…")
    _record_deployment("v1.8.1", deployed_by="ci-pipeline")
    time.sleep(1)  # small gap so timestamps are distinct

    _info("Deploying order-service:v1.8.2 (contains N+1 regression)…")
    _record_deployment("v1.8.2", deployed_by="ci-pipeline")

    _info("Activating N+1 failure flag (effect of the new code)…")
    _set_failure(n_plus_one=True)

    _ok("Bad deploy scenario ACTIVE.")
    _ok("v1.8.2 is live. N+1 queries now firing on every GET /orders request.")
    _info("Check /deployments endpoint and Grafana 'DB Queries per Request' panel.")


def scenario_red_herring_1() -> None:
    """
    Red Herring A — Harmless deploy coincides with an unrelated DB slowdown.
    - Deploy v1.8.3 (text-only change, perfectly healthy code)
    - Simultaneously inject db_slow=True (simulates lock contention from a batch job)
    Root cause: db_slow (NOT the deploy — v1.8.3 is innocent)
    Red herring: deployment event at the same timestamp tempts the agent to blame the deploy.
    Signals:  deployment event (v1.8.3) in deployments table
              db_query_duration_seconds p95 spikes immediately after deploy timestamp
              http_request_duration_seconds p95 spikes
              NO increase in error rate
              NO increase in db_queries_total / request ratio (N+1 is NOT active)
    """
    _info("Deploying order-service:v1.8.3 (harmless text change)…")
    _record_deployment("v1.8.3", deployed_by="ci-pipeline")

    _info("Injecting DB slow-query (unrelated to deploy — simulates a batch job lock)…")
    _set_failure(db_slow=True, db_slow_seconds=2.0)

    _ok("Red Herring A ACTIVE.")
    _info("True root cause: db_slow (batch job lock contention).")
    _info("Red herring: deploy event at same timestamp (v1.8.3 is innocent).")


def scenario_red_herring_2() -> None:
    """
    Red Herring B — CPU spike caused by error retry loop.
    The CPU is NOT the root cause; it is a symptom of the error spike causing
    clients to retry aggressively, which burns CPU on the server.
    Root cause: error_spike
    Red herring: process_cpu_seconds_total is high → naive diagnosis = CPU issue
    Signals:  http_errors_total rate rises (the TRUE root cause signal)
              process_cpu_seconds_total rises (the RED HERRING)
              http_request_duration_seconds unaffected (errors fail fast)
              NO memory growth
              NO DB query ratio increase
    """
    _info("Starting error spike to induce client retry load (CPU side-effect)…")
    _set_failure(error_spike=True, error_spike_rate=0.5, high_cpu=True)

    _ok("Red Herring B ACTIVE.")
    _info("True root cause: error_spike (500 errors at 50 % rate).")
    _info("Red herring: CPU elevated (effect of retry storm, not the cause).")


# ── Scenario registry ──────────────────────────────────────────────────────────

SCENARIOS: dict[str, tuple[callable, str]] = {
    "n_plus_one": (
        scenario_n_plus_one,
        "N+1 query regression — DB queries per request explodes",
    ),
    "db_slow": (
        scenario_db_slow,
        "Slow DB queries — p95 latency spikes to 2–3 s",
    ),
    "high_cpu": (
        scenario_high_cpu,
        "High CPU (symptom of error loop — root cause is error_spike)",
    ),
    "error_spike": (
        scenario_error_spike,
        "Random 500 errors at 30 % rate",
    ),
    "memory_leak": (
        scenario_memory_leak,
        "RSS grows 1 KB per request",
    ),
    "bad_deploy": (
        scenario_bad_deploy,
        "Deploy v1.8.2 (N+1 bug) over v1.8.1 + records deployment log",
    ),
    "red_herring_1": (
        scenario_red_herring_1,
        "Harmless v1.8.3 deploy coincides with db_slow (blame the deploy? Wrong.)",
    ),
    "red_herring_2": (
        scenario_red_herring_2,
        "CPU spike is a symptom of error_spike retry storm, not the root cause",
    ),
}


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(_args: argparse.Namespace) -> None:
    print("\nAvailable scenarios:\n")
    for name, (_, desc) in SCENARIOS.items():
        print(f"  {name:<20} {desc}")
    print()


def cmd_start(args: argparse.Namespace) -> None:
    name = args.scenario
    if name not in SCENARIOS:
        _die(
            f"Unknown scenario '{name}'.\n"
            f"  Run:  python scripts/scenarios.py list"
        )
    fn, desc = SCENARIOS[name]
    print(f"\n[{datetime.datetime.now().isoformat(timespec='seconds')}] "
          f"Starting scenario: {name}")
    print(f"  {desc}\n")
    fn()
    print()


def cmd_reset(_args: argparse.Namespace) -> None:
    print("\nResetting all failure flags…")
    result = _reset_failure()
    _ok("All failure flags cleared. Service is back to healthy state.")
    print(f"  Flags: {result}\n")


def cmd_status(_args: argparse.Namespace) -> None:
    failure = _get("/admin/failure")
    health = _get("/health")
    deployments = _get("/deployments?limit=5")

    print("\n── Service Health ────────────────────────────────────")
    for k, v in health.items():
        print(f"  {k}: {v}")

    print("\n── Failure Flags ─────────────────────────────────────")
    for k, v in failure.items():
        active = " ◄ ACTIVE" if v and k not in ("db_slow_seconds", "error_spike_rate") else ""
        print(f"  {k}: {v}{active}")

    print("\n── Recent Deployments ────────────────────────────────")
    if not deployments:
        print("  (none)")
    for d in deployments:
        ts = d.get("deployed_at", "")[:19]
        print(f"  [{ts}] {d['service']}@{d['version']} by {d['deployed_by']}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scenarios.py",
        description="Incident Response Agent — scenario control CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start
    p_start = sub.add_parser("start", help="Activate a failure scenario")
    p_start.add_argument(
        "scenario",
        choices=list(SCENARIOS.keys()),
        metavar="scenario_name",
        help=f"One of: {', '.join(SCENARIOS.keys())}",
    )
    p_start.set_defaults(func=cmd_start)

    # reset
    p_reset = sub.add_parser("reset", help="Reset all failure flags to healthy state")
    p_reset.set_defaults(func=cmd_reset)

    # list
    p_list = sub.add_parser("list", help="List available scenarios")
    p_list.set_defaults(func=cmd_list)

    # status
    p_status = sub.add_parser("status", help="Show current service health and failure flags")
    p_status.set_defaults(func=cmd_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
