"""Main client class for Financial Hub PostgreSQL operations."""

from typing import List, Optional

import psycopg2
from psycopg2.extensions import connection as PgConnection

from .models import CrawlTarget


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
