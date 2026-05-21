"""Main client class for Financial Hub PostgreSQL operations."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json

from .models import CrawlRun, CrawlTarget


class FinancialHubClient:
    """
    Financial Hub database client.

    Provides template operations (CRUD) for crawlers interacting
    with the Financial Hub PostgreSQL database.

    Usage:
        conn = psycopg2.connect(...)
        client = FinancialHubClient(conn)
        targets = client.get_crawl_targets(source_type="wechat")
    """

    def __init__(self, connection: PgConnection):
        """
        Initialize the client with an existing PostgreSQL connection.

        Args:
            connection: A psycopg2 connection object managed by the caller.
        """
        self._conn = connection

    @property
    def connection(self) -> PgConnection:
        """Return the underlying database connection."""
        return self._conn

    # ──────────────────────────────────────────────
    # crawl_targets queries
    # ──────────────────────────────────────────────

    def get_crawl_targets(
        self,
        source_type: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> List[CrawlTarget]:
        """
        Query the crawl_targets table and return a list of CrawlTarget objects.

        Args:
            source_type: Filter by source type (e.g. 'wechat', 'youtube', 'xiaoyuzhou').
                         If None, no filter is applied.
            enabled: Filter by enabled status. If None, no filter is applied.

        Returns:
            A list of CrawlTarget instances matching the filters.
        """
        query = "SELECT * FROM crawl_targets WHERE 1=1"
        params: list = []

        if source_type is not None:
            query += " AND source_type = %s"
            params.append(source_type)

        if enabled is not None:
            query += " AND enabled = %s"
            params.append(enabled)

        query += " ORDER BY id ASC"

        with self._conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

        return [CrawlTarget.from_row(row, columns) for row in rows]

    def get_crawl_target_by_id(self, target_id: int) -> Optional[CrawlTarget]:
        """
        Query a single crawl target by its ID.

        Args:
            target_id: The primary key ID of the target.

        Returns:
            A CrawlTarget instance, or None if not found.
        """
        query = "SELECT * FROM crawl_targets WHERE id = %s"

        with self._conn.cursor() as cur:
            cur.execute(query, (target_id,))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()

        if row is None:
            return None
        return CrawlTarget.from_row(row, columns)

    # ──────────────────────────────────────────────
    # crawl lifecycle hooks
    # ──────────────────────────────────────────────

    def notify_crawl_start(
        self,
        target_id: int,
        component_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CrawlRun:
        """
        Hook to call BEFORE a crawl begins.

        Performs the following in a single transaction:
        1. Insert a new row in crawl_runs with status='running'.
        2. Update crawl_targets.last_crawl_status to 'running'.
        3. Insert a 'crawl_start' event in system_events.
        4. UPSERT component_status to 'healthy'.

        Args:
            target_id: The crawl target ID to run against.
            component_name: The crawler component name (e.g. 'wechat_crawler').
            metadata: Optional extra metadata to attach to the system event.

        Returns:
            The newly created CrawlRun instance (caller should keep the run_id
            and pass it to notify_crawl_end later).
        """
        event_meta = {"target_id": target_id}
        if metadata:
            event_meta.update(metadata)

        with self._conn.cursor() as cur:
            # 1. Insert crawl_runs
            cur.execute(
                """
                INSERT INTO crawl_runs (target_id, status)
                VALUES (%s, 'running')
                RETURNING *
                """,
                (target_id,),
            )
            columns = [desc[0] for desc in cur.description]
            run = CrawlRun.from_row(cur.fetchone(), columns)

            # 2. Update crawl_targets
            cur.execute(
                """
                UPDATE crawl_targets
                SET last_crawl_status = 'running', updated_at = NOW()
                WHERE id = %s
                """,
                (target_id,),
            )

            # 3. Insert system_events
            cur.execute(
                """
                INSERT INTO system_events (event_type, source, message, metadata)
                VALUES ('crawl_start', %s, %s, %s)
                """,
                (
                    component_name,
                    f"Crawl started for target_id={target_id}",
                    Json(event_meta),
                ),
            )

            # 4. UPSERT component_status
            cur.execute(
                """
                INSERT INTO component_status (component_name, status, last_heartbeat, updated_at)
                VALUES (%s, 'healthy', NOW(), NOW())
                ON CONFLICT (component_name)
                DO UPDATE SET status = 'healthy', last_heartbeat = NOW(), last_error = NULL, updated_at = NOW()
                """,
                (component_name,),
            )

        self._conn.commit()
        return run

    def notify_crawl_end(
        self,
        run_id: int,
        target_id: int,
        component_name: str,
        success: bool,
        items_found: int = 0,
        items_new: int = 0,
        items_failed: int = 0,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Hook to call AFTER a crawl finishes.

        Performs the following in a single transaction:
        1. Update crawl_runs with final status and stats.
        2. Update crawl_targets with last_crawl_at, status, error, total_items.
        3. Insert a 'crawl_end' or 'crawl_error' event in system_events.
        4. UPSERT component_status (degraded if failed, healthy if success).

        Args:
            run_id: The crawl_runs.id returned by notify_crawl_start.
            target_id: The crawl target ID.
            component_name: The crawler component name.
            success: Whether the crawl succeeded.
            items_found: Total items discovered in this run.
            items_new: New items added in this run.
            items_failed: Items that failed processing.
            error_message: Error details if the crawl failed.
            duration_ms: Total run duration in milliseconds.
            metadata: Optional extra metadata for the system event.
        """
        status = "success" if success else "failed"

        event_meta: Dict[str, Any] = {
            "target_id": target_id,
            "run_id": run_id,
            "items_found": items_found,
            "items_new": items_new,
            "items_failed": items_failed,
        }
        if error_message:
            event_meta["error"] = error_message
        if metadata:
            event_meta.update(metadata)

        event_type = "crawl_end" if success else "crawl_error"
        event_msg = (
            f"Crawl {'succeeded' if success else 'failed'} for target_id={target_id}, "
            f"found={items_found}, new={items_new}, failed={items_failed}"
        )

        component_status = "healthy" if success else "degraded"

        with self._conn.cursor() as cur:
            # 1. Update crawl_runs
            cur.execute(
                """
                UPDATE crawl_runs
                SET status = %s,
                    finished_at = NOW(),
                    items_found = %s,
                    items_new = %s,
                    items_failed = %s,
                    error_message = %s,
                    duration_ms = %s
                WHERE id = %s
                """,
                (status, items_found, items_new, items_failed, error_message, duration_ms, run_id),
            )

            # 2. Update crawl_targets
            cur.execute(
                """
                UPDATE crawl_targets
                SET last_crawl_at = NOW(),
                    last_crawl_status = %s,
                    last_error = %s,
                    total_items = total_items + %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, error_message, items_new, target_id),
            )

            # 3. Insert system_events
            cur.execute(
                """
                INSERT INTO system_events (event_type, source, message, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (event_type, component_name, event_msg, Json(event_meta)),
            )

            # 4. UPSERT component_status
            cur.execute(
                """
                INSERT INTO component_status (component_name, status, last_heartbeat, last_error, updated_at)
                VALUES (%s, %s, NOW(), %s, NOW())
                ON CONFLICT (component_name)
                DO UPDATE SET status = %s, last_heartbeat = NOW(), last_error = %s, updated_at = NOW()
                """,
                (component_name, component_status, error_message, component_status, error_message),
            )

        self._conn.commit()
