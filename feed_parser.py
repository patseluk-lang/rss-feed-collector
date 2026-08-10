"""
feed_parser.py - parsing RSS 2.0 and Atom without external dependencies.

Single responsibility: XML (bytes/str) -> list of dictionaries.
No network here. No files here. Parsing only.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ATOM_NAMESPACES = {
    "http://www.w3.org/2005/Atom",   # Atom 1.0 (RFC 4287)
    "http://purl.org/atom/ns#",      # Atom 0.3 (obsolete, but still turns up)
}


class FeedParseError(Exception):
    """The XML does not parse, or it is not a feed."""


@dataclass
class FeedItem:
    title: str | None
    link: str | None
    description: str | None
    published: datetime | None
    published_raw: str | None  # the original string, if parsing failed


@dataclass
class Feed:
    source: str                       # channel name (<title>)
    format: str                       # "rss" | "atom"
    items: list[FeedItem] = field(default_factory=list)
    skipped_no_link: int = 0          # items dropped for having no URL - not in the output, but counted


# -- helpers ----------------------------------------------------------------

def _split_tag(tag: str) -> tuple[str, str]:
    """'{uri}local' -> ('uri', 'local'); 'local' -> ('', 'local')"""
    if tag.startswith("{"):
        uri, _, local = tag[1:].partition("}")
        return uri, local
    return "", tag


def _text(el: ET.Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    value = el.text.strip()
    return value or None


def _find(parent: ET.Element, local_name: str, ns: str) -> ET.Element | None:
    """Finds a direct child by local name, taking the namespace into account."""
    qname = f"{{{ns}}}{local_name}" if ns else local_name
    return parent.find(qname)


def _findall(parent: ET.Element, local_name: str, ns: str) -> list[ET.Element]:
    qname = f"{{{ns}}}{local_name}" if ns else local_name
    return parent.findall(qname)


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(raw: str | None) -> str | None:
    """
    Strips HTML tags and collapses whitespace.

    Unescaping happens EXACTLY ONCE. That is deliberate.
    Some feeds escape twice (&amp;amp;), and a second pass would "fix" them
    while corrupting correct data: the title "How to write &amp; in HTML"
    must stay "How to write &amp; in HTML" rather than turning into "&".
    A bug in the source should stay visible, not be silently patched over.
    """
    if raw is None:
        return None
    text = html.unescape(raw)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def parse_date(raw: str | None) -> tuple[datetime | None, str | None]:
    """
    Returns (datetime, None) on success, or (None, original_string) on failure.
    Tries RFC 822 (RSS) and ISO 8601 (Atom) regardless of the feed format:
    real feeds violate the spec in both directions.
    """
    if not raw:
        return None, None
    raw = raw.strip()

    # RFC 822: Mon, 13 Jul 2026 09:00:00 +0000
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt, None
    except (TypeError, ValueError):
        pass

    # ISO 8601: 2026-07-13T09:00:00Z
    iso = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt, None
    except ValueError:
        pass

    return None, raw


# -- RSS 2.0 ----------------------------------------------------------------

def _parse_rss(root: ET.Element, ns: str) -> Feed:
    channel = _find(root, "channel", ns)
    if channel is None:
        raise FeedParseError("RSS feed with no <channel>")

    source = clean_text(_text(_find(channel, "title", ns))) or "(untitled feed)"
    feed = Feed(source=source, format="rss")

    for item in _findall(channel, "item", ns):
        link = clean_text(_text(_find(item, "link", ns)))
        if not link:
            # Without a URL the entry is useless to the client. Drop it, but count it:
            # silent data loss is worse than data visibly missing.
            feed.skipped_no_link += 1
            continue

        published, published_raw = parse_date(_text(_find(item, "pubDate", ns)))
        feed.items.append(
            FeedItem(
                title=clean_text(_text(_find(item, "title", ns))),
                link=link,
                description=clean_text(_text(_find(item, "description", ns))),
                published=published,
                published_raw=published_raw,
            )
        )
    return feed


# -- Atom -------------------------------------------------------------------

def _atom_link(entry: ET.Element, ns: str) -> str | None:
    """
    In Atom, <link> is an href attribute, not text.
    There may be several <link> elements; the one we want is rel="alternate".
    Per RFC 4287, a missing rel means alternate.
    """
    candidates = _findall(entry, "link", ns)
    for el in candidates:
        rel = el.get("rel")
        if rel is None or rel == "alternate":
            href = el.get("href")
            if href:
                return html.unescape(href)
    # fallback: any href at all
    for el in candidates:
        href = el.get("href")
        if href:
            return html.unescape(href)
    return None


def _parse_atom(root: ET.Element, ns: str) -> Feed:
    source = clean_text(_text(_find(root, "title", ns))) or "(untitled feed)"
    feed = Feed(source=source, format="atom")

    for entry in _findall(root, "entry", ns):
        link = _atom_link(entry, ns)
        if not link:
            feed.skipped_no_link += 1
            continue

        # <published> is more precise than <updated>, but it is optional
        raw_date = _text(_find(entry, "published", ns)) or _text(_find(entry, "updated", ns))
        published, published_raw = parse_date(raw_date)

        # <summary> is shorter; <content> is the fallback
        body = _text(_find(entry, "summary", ns)) or _text(_find(entry, "content", ns))

        feed.items.append(
            FeedItem(
                title=clean_text(_text(_find(entry, "title", ns))),
                link=link,
                description=clean_text(body),
                published=published,
                published_raw=published_raw,
            )
        )
    return feed


# -- entry point ------------------------------------------------------------

def parse_feed(data: bytes | str) -> Feed:
    """
    Parses feed content. Raises FeedParseError if this is not valid RSS/Atom.
    """
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise FeedParseError(f"XML does not parse: {exc}") from exc

    ns, local = _split_tag(root.tag)

    if local == "rss":
        return _parse_rss(root, ns)

    if local == "feed":
        if ns and ns not in ATOM_NAMESPACES:
            raise FeedParseError(f"<feed> with an unknown namespace: {ns}")
        return _parse_atom(root, ns)

    raise FeedParseError(f"unknown root element: <{local}>")
