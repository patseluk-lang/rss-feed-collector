# RSS Feed Collector

A small command-line utility that reads a list of RSS/Atom feeds, downloads
each one, and writes all articles into a single readable text file.

No external dependencies — pure Python standard library. No database, no
hosting, no web scraping. Just: list of URLs in, one text file out.

---

## Requirements

- Python 3.9 or newer. Nothing else to install.

Check your version:

```
python --version
```

---

## Quick start

1. Put your feed URLs in `feeds.txt` — one per line:

   ```
   https://example.com/feed.xml
   https://another-site.example.com/rss
   ```

2. Run:

   ```
   python collector.py
   ```

3. Find the result in `output/RSS_EXPORT_YYYY-MM-DD.txt`.

That's it.

---

## Output format

Each article becomes one block, exactly as specified:

```
SOURCE: LP-HIRE CORE
DATE: 2026-07-13
TITLE: Example Article Title
URL: https://example.com/article
DESCRIPTION: Article summary text
--------------------------------
```

See `sample_output.txt` for a full example produced from test feeds. That
sample deliberately includes messy cases (a malformed date, a missing
description, non-ASCII text) so you can see how the tool handles imperfect
feeds, not just the happy path.

---

## Configuration

Feeds are listed in `feeds.txt` (plain text):

- one URL per line;
- blank lines are ignored;
- lines starting with `#` are comments.

Add or remove a feed by editing this file. Nothing else to change.

Both **RSS 2.0** and **Atom** feeds are supported; the format is detected
automatically per feed.

---

## Options

```
python collector.py [options]
```

| Option | Default | Meaning |
|--------|---------|---------|
| `--config PATH`  | `feeds.txt` | file with the list of feed URLs |
| `--out-dir PATH` | `output`    | folder for the result file |
| `--only-new`     | off         | write only articles not seen in previous runs |
| `--state PATH`   | `seen.json` | memory file used by `--only-new` |

### About `--only-new`

By default the tool writes **every** article from every feed on each run —
a predictable full snapshot.

With `--only-new`, it remembers which articles it has already exported (by
URL, in `seen.json`) and writes only new ones on later runs. To reset this
memory, delete `seen.json`.

---

## What happens when a feed fails

One broken or unreachable feed does **not** stop the others. The feed is
skipped, and a summary at the end lists exactly what succeeded and what
failed, with the reason:

```
============================================================
SUMMARY
============================================================
  [OK]      LP-HIRE CORE: 3 records
  [OK]      Nordic Labour Digest: 2 records
  [ERROR]   https://broken.example.com/feed
            HTTP 404 Not Found
------------------------------------------------------------
  Feeds: 3 | ok: 2 | failed: 1
  Total records: 5
============================================================
```

The program exits with code `0` if at least one feed succeeded, `1` if all
feeds failed (useful for scheduled runs).

---

## Design notes (decisions made where the brief was silent)

The brief left a few things unspecified. Choices made, and why:

- **Dates.** Parsed to `YYYY-MM-DD` when possible (matching the example in
  the brief). If a feed's date is malformed, the *original* string is kept
  rather than dropping the article.

- **Descriptions.** HTML tags are stripped and whitespace collapsed to keep
  the output readable. HTML entities are decoded once — not twice — so
  correctly-escaped titles are never corrupted.

- **Articles with no URL** are skipped (a link is essential), but counted
  and reported — silent data loss is avoided.

- **Articles with no title** are kept (a link plus description is still
  useful) and shown with `(none)`.

- **Encoding** is always UTF-8, explicitly, so non-English text survives on
  Windows.

- **`--only-new` is off by default.** A first run should give a full
  snapshot; opt into deltas explicitly.

---

## Files

| File | Purpose |
|------|---------|
| `collector.py`   | main entry point (run this) |
| `fetcher.py`     | downloads feeds (timeouts, size cap) |
| `feed_parser.py` | parses RSS 2.0 and Atom |
| `state.py`       | `--only-new` memory (`seen.json`) |
| `writer.py`      | formats the output blocks |
| `feeds.txt`      | your list of feeds (edit this) |
| `sample_output.txt` | example result |
| `fixtures/`      | test feeds used for the sample |
