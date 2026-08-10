"""
writer.py - formatting records into a text file.

The block format follows the brief's sample exactly:

    SOURCE: LP-HIRE CORE
    DATE: 2026-07-13
    TITLE: Example Article Title
    URL: https://example.com/article
    DESCRIPTION: Article summary text
    --------------------------------

SOURCE and DATE repeat in every block - that is how the client's sample looks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

SEPARATOR = "-" * 32
PLACEHOLDER = "(none)"   # for missing fields: an explicit marker beats a blank


@dataclass
class OutputRow:
    source: str
    date: str          # already formatted as a string
    title: str
    url: str
    description: str


def format_date(dt: datetime | None, raw: str | None) -> str:
    """
    ISO date if it parsed; otherwise the original string (decision #1:
    keep the original rather than drop the record); otherwise a placeholder.
    """
    if dt is not None:
        return dt.strftime("%Y-%m-%d")
    if raw:
        return raw
    return PLACEHOLDER


def build_row(source: str, item) -> OutputRow:
    """item is a FeedItem from feed_parser."""
    return OutputRow(
        source=source or PLACEHOLDER,
        date=format_date(item.published, item.published_raw),
        title=item.title or PLACEHOLDER,
        url=item.link or PLACEHOLDER,
        description=item.description or PLACEHOLDER,
    )


def render_block(row: OutputRow) -> str:
    return (
        f"SOURCE: {row.source}\n"
        f"DATE: {row.date}\n"
        f"TITLE: {row.title}\n"
        f"URL: {row.url}\n"
        f"DESCRIPTION: {row.description}\n"
        f"{SEPARATOR}\n"
    )


def render_document(rows: list[OutputRow], header: str | None = None) -> str:
    parts = []
    if header:
        parts.append(header.rstrip() + "\n\n")
    for row in rows:
        parts.append(render_block(row))
    return "".join(parts)
