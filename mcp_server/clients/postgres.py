from typing import Any

import psycopg
from psycopg.rows import dict_row

from ..config import DATABASE_URL


def get_database_stats() -> dict[str, Any]:
    """Read active database connections and basic table statistics."""

    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    pid,
                    usename,
                    application_name,
                    client_addr,
                    state,
                    wait_event_type,
                    wait_event,
                    query_start,
                    state_change,
                    LEFT(query, 500) AS query
                FROM pg_stat_activity
                WHERE pid <> pg_backend_pid()
                ORDER BY query_start DESC NULLS LAST
                """
            )

            connections = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    schemaname,
                    relname AS table_name,
                    seq_scan,
                    seq_tup_read,
                    idx_scan,
                    idx_tup_fetch,
                    n_live_tup,
                    n_dead_tup,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze
                FROM pg_stat_user_tables
                ORDER BY n_dead_tup DESC
                LIMIT 100
                """
            )

            table_stats = cursor.fetchall()

    return {
        "active_connections": len(connections),
        "connections": connections,
        "table_stats": table_stats,
    }


def get_slow_queries(limit: int) -> list[dict[str, Any]]:
    """Read query performance information from pg_stat_statements."""

    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    queryid,
                    LEFT(query, 1000) AS query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    rows,
                    shared_blks_hit,
                    shared_blks_read
                FROM pg_stat_statements
                ORDER BY mean_exec_time DESC
                LIMIT %s
                """,
                (limit,),
            )

            return cursor.fetchall()


def get_recent_deployments(
    service: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Read recent deployments for a service."""

    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    service,
                    version,
                    commit_sha,
                    deployed_by,
                    deployed_at,
                    notes
                FROM deployments
                WHERE service = %s
                ORDER BY deployed_at DESC
                LIMIT %s
                """,
                (service, limit),
            )

            return cursor.fetchall()