import httpx

from ..config import PROMETHEUS_URL


def query_prometheus(
    promql: str,
    start: str,
    end: str,
    step: str,
) -> dict:
    """Execute a Prometheus range query."""

    response = httpx.get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        params={
            "query": promql,
            "start": start,
            "end": end,
            "step": step,
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(
            payload.get("error", "Prometheus query failed")
        )

    return payload["data"]