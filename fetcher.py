"""
fetcher.py - downloading feeds over the network.

Single responsibility: URL -> bytes (or a clear error).
No parsing happens here.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

TIMEOUT_SECONDS = 30      # socket silence longer than this - we cut it off
MAX_BYTES = 10 * 1024 * 1024   # 10 MB: a feed never weighs that much; more means a config mistake
USER_AGENT = "RSS-Collector/1.0 (+https://example.com/contact)"


class FetchError(Exception):
    """Feed is unreachable. The message is fit to show to a user."""


@dataclass
class FetchResult:
    url: str
    data: bytes


def _fetch_file(url: str) -> bytes:
    """Local file - for the test harness and offline checks."""
    path = Path(url[7:]) if url.startswith("file://") else Path(url)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise FetchError(f"file is not readable: {exc}") from exc


def fetch(url: str, timeout: int = TIMEOUT_SECONDS) -> FetchResult:
    """
    Downloads the content at the URL. Raises FetchError with a human message.

    Supports http/https and local files (for the test harness).
    """
    scheme = urlparse(url).scheme

    if scheme in ("", "file"):
        return FetchResult(url=url, data=_fetch_file(url))

    if scheme not in ("http", "https"):
        raise FetchError(f"unsupported scheme: {scheme!r}")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # read(N+1) rather than read(): if the server hands back gigabytes,
            # a plain read() would pull all of it into memory.
            data = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"network unreachable: {exc.reason}") from exc
    except socket.timeout as exc:
        raise FetchError(f"timed out after {timeout}s") from exc
    except OSError as exc:
        raise FetchError(f"connection error: {exc}") from exc

    if len(data) > MAX_BYTES:
        raise FetchError(
            f"response larger than {MAX_BYTES // 1024 // 1024} MB - "
            f"this does not look like an RSS feed, check the URL"
        )

    if not data.strip():
        raise FetchError("server returned an empty response")

    return FetchResult(url=url, data=data)
