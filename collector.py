"""
collector.py - main entry point.

Reads a list of feeds from the config, downloads each one, parses it,
formats and writes the result to a text file. One unreachable or malformed
feed does not stop the rest; a summary is printed at the end.

Usage:
    python collector.py
    python collector.py --config feeds.txt --out-dir output
    python collector.py --only-new
    python collector.py --help
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from fetcher import fetch, FetchError
from feed_parser import parse_feed, FeedParseError
from state import SeenStore
from writer import build_row, render_document


def load_config(path: Path) -> list[str]:
    """
    feeds.txt: one URL per line. Blank lines and lines starting with '#' are ignored.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Create it: one feed URL per line ('#' starts a comment)."
        )
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def process_feed(url: str, seen: SeenStore | None) -> tuple[list, dict]:
    """
    Processes one feed. Returns (rows_for_output, stats).
    Never raises upwards - every failure ends up in the stats.
    """
    stats = {"url": url, "source": None, "written": 0,
             "skipped_seen": 0, "skipped_no_link": 0, "error": None}
    rows = []

    try:
        result = fetch(url)
        feed = parse_feed(result.data)
    except (FetchError, FeedParseError) as exc:
        stats["error"] = str(exc)
        return rows, stats

    stats["source"] = feed.source
    stats["skipped_no_link"] = feed.skipped_no_link

    for item in feed.items:
        if seen is not None and not seen.is_new(item.link):
            stats["skipped_seen"] += 1
            continue
        rows.append(build_row(feed.source, item))
        if seen is not None:
            seen.mark(item.link)

    stats["written"] = len(rows)
    return rows, stats


def print_summary(all_stats: list[dict], out_path: Path, total_rows: int) -> None:
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for s in all_stats:
        name = s["source"] or s["url"]
        if s["error"]:
            print(f"  [FAILED]  {name}")
            print(f"            {s['error']}")
        else:
            line = f"  [OK]      {name}: {s['written']} items"
            extra = []
            if s["skipped_seen"]:
                extra.append(f"{s['skipped_seen']} already seen")
            if s["skipped_no_link"]:
                extra.append(f"{s['skipped_no_link']} with no URL")
            if extra:
                line += f" ({', '.join(extra)})"
            print(line)
    print("-" * 60)
    ok = sum(1 for s in all_stats if not s["error"])
    failed = len(all_stats) - ok
    print(f"  Feeds: {len(all_stats)} | succeeded: {ok} | failed: {failed}")
    print(f"  Items total: {total_rows}")
    if total_rows:
        print(f"  File: {out_path}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collects RSS/Atom feeds into a single text file."
    )
    parser.add_argument("--config", type=Path, default=Path("feeds.txt"),
                        help="file with the list of URLs (default: feeds.txt)")
    parser.add_argument("--out-dir", type=Path, default=Path("output"),
                        help="where to put the result (default: output/)")
    parser.add_argument("--only-new", action="store_true",
                        help="new articles only (state kept in seen.json)")
    parser.add_argument("--state", type=Path, default=Path("seen.json"),
                        help="state file for --only-new (default: seen.json)")
    args = parser.parse_args(argv)

    try:
        urls = load_config(args.config)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not urls:
        print(f"No URLs found in {args.config}.", file=sys.stderr)
        return 1

    seen = None
    if args.only_new:
        seen = SeenStore(args.state)
        seen.load()

    all_rows = []
    all_stats = []
    for url in urls:
        rows, stats = process_feed(url, seen)
        all_rows.extend(rows)
        all_stats.append(stats)

    out_path = args.out_dir / f"RSS_EXPORT_{date.today().isoformat()}.txt"

    if all_rows:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        # encoding='utf-8' explicitly: without it Windows writes cp1251
        # and crashes on non-ASCII (Swedish, Ukrainian and so on).
        out_path.write_text(render_document(all_rows), encoding="utf-8")

    if seen is not None:
        seen.save()

    print_summary(all_stats, out_path, len(all_rows))

    # Exit code: 0 if at least one feed succeeded, 1 if all of them failed.
    any_ok = any(not s["error"] for s in all_stats)
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(main())
