import json
from functools import wraps
from typing import Any, Callable

from mcp.server import MCPServer

from .audit import audit_log
from .clients.git import (
    get_commit_diff as git_get_commit_diff,
    get_recent_commits as git_get_recent_commits,
)
from .clients.loki import query_loki
from .clients.postgres import (
    get_database_stats as postgres_get_database_stats,
    get_recent_deployments as postgres_get_recent_deployments,
    get_slow_queries as postgres_get_slow_queries,
)
from .clients.prometheus import query_prometheus

from .models import (
    CommitDiffInput,
    CommitDiffOutput,
    CommitsInput,
    CommitsOutput,
    DatabaseStatsInput,
    DatabaseStatsOutput,
    DeploymentsInput,
    DeploymentsOutput,
    LogsInput,
    LogsOutput,
    MetricsInput,
    MetricsOutput,
    SlowQueriesInput,
    SlowQueriesOutput,
)


mcp = MCPServer(
    "incident-observability",
    instructions=(
        "Read-only observability tools for investigating "
        "production incidents. Never assume or fabricate "
        "observability data."
    ),
)


def _serialize(value: Any) -> str:
    return json.dumps(
        value,
        default=str,
        ensure_ascii=False,
    )


def _audit(
    tool_name: str,
    args: dict[str, Any],
    result: Any,
) -> None:

    try:
        size = len(_serialize(result).encode("utf-8"))

        audit_log(
            tool=tool_name,
            args=args,
            result_size=size,
        )

    except Exception:
        # Auditing should never crash an otherwise successful
        # observability query.
        pass


@mcp.tool()
def get_metrics(
    input: MetricsInput,
) -> MetricsOutput:
    """Query Prometheus metrics using a PromQL range query."""

    try:
        result = query_prometheus(
            promql=input.promql,
            start=input.start,
            end=input.end,
            step=input.step,
        )

        output = MetricsOutput(
            success=True,
            result_type=result.get("resultType"),
            result=result.get("result"),
        )

    except Exception as exc:

        output = MetricsOutput(
            success=False,
            error=f"Prometheus query failed: {exc}",
        )

    _audit(
        "get_metrics",
        input.model_dump(),
        output,
    )

    return output


@mcp.tool()
def search_logs(
    input: LogsInput,
) -> LogsOutput:
    """Search Loki logs using a LogQL range query."""

    try:
        result = query_loki(
            logql=input.logql,
            start=input.start,
            end=input.end,
            limit=input.limit,
        )

        output = LogsOutput(
            success=True,
            result_type=result.get("resultType"),
            result=result.get("result"),
        )

    except Exception as exc:

        output = LogsOutput(
            success=False,
            error=f"Loki query failed: {exc}",
        )

    _audit(
        "search_logs",
        input.model_dump(),
        output,
    )

    return output


@mcp.tool()
def get_database_stats(
    input: DatabaseStatsInput,
) -> DatabaseStatsOutput:
    """Read PostgreSQL activity and basic table statistics."""

    try:
        result = postgres_get_database_stats()

        output = DatabaseStatsOutput(
            success=True,
            active_connections=result["active_connections"],
            connections=result["connections"],
            table_stats=result["table_stats"],
        )

    except Exception as exc:

        output = DatabaseStatsOutput(
            success=False,
            error=f"Database stats query failed: {exc}",
        )

    _audit(
        "get_database_stats",
        input.model_dump(),
        output,
    )

    return output


@mcp.tool()
def get_slow_queries(
    input: SlowQueriesInput,
) -> SlowQueriesOutput:
    """Read slow PostgreSQL queries from pg_stat_statements."""

    try:
        queries = postgres_get_slow_queries(
            limit=input.limit,
        )

        output = SlowQueriesOutput(
            success=True,
            queries=queries,
        )

    except Exception as exc:

        output = SlowQueriesOutput(
            success=False,
            error=f"Slow query lookup failed: {exc}",
        )

    _audit(
        "get_slow_queries",
        input.model_dump(),
        output,
    )

    return output


@mcp.tool()
def get_recent_deployments(
    input: DeploymentsInput,
) -> DeploymentsOutput:
    """Read recent deployments for a service."""

    try:
        deployments = postgres_get_recent_deployments(
            service=input.service,
            limit=input.limit,
        )

        output = DeploymentsOutput(
            success=True,
            deployments=deployments,
        )

    except Exception as exc:

        output = DeploymentsOutput(
            success=False,
            error=f"Deployment lookup failed: {exc}",
        )

    _audit(
        "get_recent_deployments",
        input.model_dump(),
        output,
    )

    return output


@mcp.tool()
def get_recent_commits(
    input: CommitsInput,
) -> CommitsOutput:
    """Read recent Git commits associated with a service."""

    try:
        commits = git_get_recent_commits(
            service=input.service,
            limit=input.limit,
        )

        output = CommitsOutput(
            success=True,
            commits=commits,
        )

    except Exception as exc:

        output = CommitsOutput(
            success=False,
            error=f"Git commit lookup failed: {exc}",
        )

    _audit(
        "get_recent_commits",
        input.model_dump(),
        output,
    )

    return output


@mcp.tool()
def get_commit_diff(
    input: CommitDiffInput,
) -> CommitDiffOutput:
    """Read the diff and metadata for a specific Git commit."""

    try:
        diff = git_get_commit_diff(
            sha=input.sha,
        )

        output = CommitDiffOutput(
            success=True,
            sha=input.sha,
            diff=diff,
        )

    except Exception as exc:

        output = CommitDiffOutput(
            success=False,
            sha=input.sha,
            error=f"Git diff lookup failed: {exc}",
        )

    _audit(
        "get_commit_diff",
        input.model_dump(),
        output,
    )

    return output


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
    )