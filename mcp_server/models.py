from typing import Any
from pydantic import BaseModel, Field


class ToolError(BaseModel):
    success: bool = False
    error: str


class MetricsInput(BaseModel):
    promql: str = Field(
        ...,
        description="PromQL expression to execute.",
    )

    start: str = Field(
        ...,
        description="Start timestamp accepted by Prometheus.",
    )

    end: str = Field(
        ...,
        description="End timestamp accepted by Prometheus.",
    )

    step: str = Field(
        ...,
        description="Prometheus query resolution such as 15s, 1m, or 5m.",
    )


class MetricsOutput(BaseModel):
    success: bool
    result_type: str | None = None
    result: Any = None
    error: str | None = None


class LogsInput(BaseModel):
    logql: str = Field(
        ...,
        description="LogQL query used to search Loki.",
    )

    start: str = Field(
        ...,
        description="Start timestamp for the log query.",
    )

    end: str = Field(
        ...,
        description="End timestamp for the log query.",
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Maximum number of log entries.",
    )


class LogsOutput(BaseModel):
    success: bool
    result_type: str | None = None
    result: Any = None
    error: str | None = None


class DatabaseStatsInput(BaseModel):
    pass


class DatabaseStatsOutput(BaseModel):
    success: bool
    active_connections: int | None = None
    connections: list[dict[str, Any]] = Field(default_factory=list)
    table_stats: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class SlowQueriesInput(BaseModel):
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of slow queries.",
    )


class SlowQueriesOutput(BaseModel):
    success: bool
    queries: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class DeploymentsInput(BaseModel):
    service: str = Field(
        ...,
        min_length=1,
        description="Service name.",
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of deployments.",
    )


class DeploymentsOutput(BaseModel):
    success: bool
    deployments: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class CommitsInput(BaseModel):
    service: str = Field(
        ...,
        min_length=1,
        description="Service whose git history should be inspected.",
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of commits.",
    )


class CommitsOutput(BaseModel):
    success: bool
    commits: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class CommitDiffInput(BaseModel):
    sha: str = Field(
        ...,
        min_length=7,
        description="Git commit SHA.",
    )


class CommitDiffOutput(BaseModel):
    success: bool
    sha: str | None = None
    diff: str | None = None
    error: str | None = None