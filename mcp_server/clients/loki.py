import httpx

from ..config import LOKI_URL


def query_loki(
    logql: str,
    start: str,
    end: str,
    limit: int,
) -> dict:
    """Execute a Loki range query."""

    response = httpx.get(
        f"{LOKI_URL}/loki/api/v1/query_range",
        params={
            "query": logql,
            "start": start,
            "end": end,
            "limit": limit,
            "direction": "backward",
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(
            payload.get("error", "Loki query failed")
        )

    return payload["data"]