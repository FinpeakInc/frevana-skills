#!/usr/bin/env python3
"""Site Data Collector — URL-list mode.

Given a list of website URLs (e.g. the `website` column from a Google Map Search
export), visit each ONE through your logged-in browser ('frevana fetch') and pull out
its social / contact links — Facebook page first, plus Instagram / LinkedIn / X /
email. Writes a CSV. Each site is fetched exactly once (first-party, through the
extension = your own IP), so there is no single site to rate-limit.

Fill in URLS below (the agent bakes these from the Maps results), or pass --input
CSV/txt to override. Run it with:  python3 extract_links.py --output leads.csv

FREVANA_CMD overrides the CLI (defaults to the globally-installed 'frevana').
"""
from __future__ import annotations

import argparse
import csv
import html as _html
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

# --- INPUT: the website URLs to visit. The agent fills this from the Maps results.
#     (Override at run time with --input pointing at a CSV that has a 'website'
#     column, or a .txt with one URL per line.)
URLS: list[str] = [
    # "https://www.example.com/",
]

# --- What to extract from each site. Keyed column name -> matcher. Facebook first.
FREVANA = os.environ.get("FREVANA_CMD", "frevana").split()

_A_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
# Social matchers: host substring -> (column, path-must-look-like-a-handle)
_SOCIAL = [
    ("facebook_url", ("facebook.com", "fb.com"), ("sharer", "share.php", "/plugins/", "/dialog/", "/tr", "l.php", "/hashtag/", "/events/", "/photo", "/login", "/help", "/policies")),
    ("instagram_url", ("instagram.com",), ("/p/", "/explore/", "/accounts/")),
    ("linkedin_url", ("linkedin.com",), ("/shareArticle", "/sharing/", "/feed/")),
    ("twitter_url", ("twitter.com", "x.com"), ("/intent/", "/share", "/hashtag/", "/search")),
]
_BARE = ("", "home.php", "pages", "sharer.php", "share.php", "tr", "intent", "sharing")
COLUMNS = [c for c, _, _ in _SOCIAL] + ["email"]

# The extension connection can blip during a long batch; retry transient failures.
_TRANSIENT = ("not connected", "transport", "socket", "timed out", "timeout",
              "econnrefused", "disconnected", "no response")
_RETRIES = 4


def _fetch_once(url: str) -> str:
    p = subprocess.run(
        [*FREVANA, "fetch", url, "--timeout", "20000"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "fetch failed").strip())
    return p.stdout


def fetch_html(url: str) -> str:
    last = None
    for attempt in range(1, _RETRIES + 1):
        try:
            return _fetch_once(url)
        except Exception as e:  # noqa: BLE001
            last = e
            if not any(t in str(e).lower() for t in _TRANSIENT) or attempt == _RETRIES:
                raise
            time.sleep(0.8 * attempt)
    raise last  # unreachable


def _clean(u: str) -> str:
    u = _html.unescape(u).strip().split("#")[0]
    if u.lower().startswith("//"):
        u = "https:" + u
    return u.rstrip("/")


def extract(html: str) -> dict[str, str]:
    out = {c: "" for c in COLUMNS}
    hrefs = [_clean(m.group(1)) for m in _A_HREF.finditer(html)]
    for col, hosts, exclude in _SOCIAL:
        for href in hrefs:
            low = href.lower()
            if not any(h in low for h in hosts):
                continue
            if any(x in low for x in exclude):
                continue
            try:
                path = urlparse(href).path.strip("/")
            except ValueError:
                continue
            head = path.split("/")[0].lower()
            if head in _BARE:
                continue
            out[col] = href if "profile.php" in low else href.split("?")[0]
            break
    m = _EMAIL.search(re.sub(r"<[^>]+>", " ", html))  # avoid matching inside tags/urls
    if m and "@" in m.group(0) and not m.group(0).lower().endswith((".png", ".jpg", ".gif")):
        out["email"] = m.group(0)
    return out


def load_urls(path: str | None) -> list[str]:
    if not path:
        return [u for u in URLS if u.strip()]
    with open(path, newline="", encoding="utf-8-sig") as f:
        head = f.read(1)
        f.seek(0)
        if head and path.lower().endswith(".csv"):
            rows = list(csv.DictReader(f))
            col = next((c for c in ("website", "url", "link") if rows and c in rows[0]), None)
            if not col:
                sys.exit("input CSV needs a website/url/link column")
            return [r[col].strip() for r in rows if r.get(col, "").strip()]
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="CSV (website/url column) or .txt (one URL/line); default = embedded URLS")
    ap.add_argument("--output", default="links.csv")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    urls = load_urls(args.input)
    if args.limit:
        urls = urls[: args.limit]
    if not urls:
        sys.exit("No URLs. Fill in URLS[] or pass --input.")

    fields = ["website"] + COLUMNS + ["status"]
    hit = 0
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for i, url in enumerate(urls, 1):
            row = {"website": url, "status": ""}
            try:
                data = extract(fetch_html(url))
                row.update(data)
                row["status"] = "ok" if data.get("facebook_url") else "no facebook"
                if data.get("facebook_url"):
                    hit += 1
            except Exception as e:  # noqa: BLE001
                row["status"] = f"error: {str(e).splitlines()[-1][:70]}"
            w.writerow(row)
            f.flush()
            print(f"[{i}/{len(urls)}] {urlparse(url).netloc[:32]:32} -> {row['status']}", file=sys.stderr)
            time.sleep(args.sleep)

    print(f"done: {hit}/{len(urls)} have a Facebook page -> {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
