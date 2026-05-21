"""Data models for Financial Hub database tables."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CrawlTarget:
    """Represents a row in the crawl_targets table."""

    id: int
    source_type: str
    target_name: str
    target_identifier: str
    enabled: bool = True
    cron_expression: str = "0 */6 * * *"
    last_crawl_at: Optional[datetime] = None
    last_crawl_status: Optional[str] = None
    last_error: Optional[str] = None
    total_items: int = 0
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: tuple, columns: list) -> "CrawlTarget":
        """Create a CrawlTarget instance from a database row."""
        data = dict(zip(columns, row))
        return cls(**data)
