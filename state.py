"""
state.py - memory between runs: which articles have already been seen.

seen.json is NOT a database (the brief forbids one). It is a plain JSON file
holding a list of normalised URLs. The format is human-readable, editable by
hand, and can be deleted to reset everything.

Single responsibility: URL normalisation + reading/writing the state.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Tracking parameters. They do not affect which article this is, so they are
# stripped during normalisation. The list is deliberately short and
# conservative: any unknown parameter is kept, because it may be a real ?id=...
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "_hsenc", "_hsmi",
}


def normalize_url(url: str) -> str:
    """
    Cautious normalisation for comparison, NOT for display.

    It does:
      - lowercase the scheme and the host
      - strip a trailing '/' from the path
      - drop KNOWN tracking parameters

    It does not:
      - touch other parameters (?id=123 stays; it may be the article key)
      - touch the #fragment
      - change the case of the path (some servers are case-sensitive)
    """
    parts = urlsplit(url.strip())

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS]
    query = urlencode(kept)

    return urlunsplit((scheme, netloc, path, query, parts.fragment))


class SeenStore:
    """The set of already-seen URLs, persisted as JSON."""

    def __init__(self, path: Path):
        self.path = path
        self._seen: set[str] = set()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._seen = set(raw.get("seen", []))
        except (json.JSONDecodeError, OSError):
            # A corrupted state file must not kill the run: the worst outcome
            # is a few duplicate exports, not lost data.
            self._seen = set()

    def save(self) -> None:
        payload = {"seen": sorted(self._seen)}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_new(self, url: str) -> bool:
        return normalize_url(url) not in self._seen

    def mark(self, url: str) -> None:
        self._seen.add(normalize_url(url))
