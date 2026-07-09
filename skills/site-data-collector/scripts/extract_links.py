#!/usr/bin/env python3
"""Site Data Collector — URL-list mode.

Given a list of website URLs (e.g. the `website` column from a Google Map Search),
visit each ONE through your logged-in browser ('frevana fetch') and pull out its
social / contact links — Facebook page first, plus Instagram / LinkedIn / X / email.
Writes a CSV. Each site is fetched exactly once (first-party, through the extension =
your own IP), so there is no single site to rate-limit.

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

FREVANA = os.environ.get("FREVANA_CMD", "frevana").split()

# Social matchers: column -> (domains matched by HOSTNAME, first-path-segments that
# are NOT a real page). Facebook first. Matching on hostname (not a substring of the
# whole URL) avoids "x.com" hitting netfli-x.com / fede-x.com; the bad-segment set is
# compared to the first path segment so "/tr" can't kill facebook.com/TravelAgency.
_SOCIAL = [
    ("facebook_url", ("facebook.com", "fb.com"),
     {"sharer", "sharer.php", "share.php", "share", "dialog", "plugins", "tr",
      "hashtag", "events", "photo.php", "photo", "login.php", "login", "help",
      "policies", "story.php", "watch", "l.php", "recover"}),
    ("instagram_url", ("instagram.com",),
     {"p", "reel", "reels", "explore", "accounts", "stories", "direct"}),
    ("linkedin_url", ("linkedin.com",),
     {"sharearticle", "sharing", "sharearticle", "feed", "cws", "uas", "login"}),
    ("twitter_url", ("twitter.com", "x.com"),
     {"intent", "share", "hashtag", "search", "home", "i", "login", "privacy",
      "tos", "explore", "notifications", "messages"}),
]
COLUMNS = [c for c, _, _ in _SOCIAL] + ["email"]

_A_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
_TAG = re.compile(r"<[^>]+>")
# Emails that belong to page tooling / vendors / placeholders, not the business.
_EMAIL_DENY = (
    "sentry.io", ".ingest.", "wixpress.com", "example.com", "example.org",
    "yourdomain", "your-email", "domain.com", "email@", "test@", "sentry-",
    "@2x", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", "godaddy.com",
    "squarespace.com", "wordpress.com", "cloudflare", "no-reply@", "noreply@",
)


def _fetch_once(url: str) -> str:
    try:
        p = subprocess.run(
            [*FREVANA, "fetch", url, "--timeout", "20000"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,  # hard bound so a wedged CLI/daemon can't hang the whole batch
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("fetch timed out")
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "").strip() or "fetch failed")
    return p.stdout


_TRANSIENT = ("not connected", "transport", "socket", "timed out", "timeout",
              "econnrefused", "disconnected", "no response")
_RETRIES = 4


def fetch_html(url: str) -> str:
    last: "Exception | None" = None
    for attempt in range(1, _RETRIES + 1):
        try:
            return _fetch_once(url)
        except Exception as e:  # noqa: BLE001
            last = e
            if not any(t in str(e).lower() for t in _TRANSIENT) or attempt == _RETRIES:
                raise
            time.sleep(0.8 * attempt)
    assert last is not None
    raise last


def _host(href: str) -> str:
    try:
        return (urlparse(href if "//" in href else "//" + href).hostname or "").lower().lstrip(".")
    except ValueError:
        return ""


def _in_domain(host: str, domains: "tuple[str, ...]") -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def _bad_email(addr: str) -> bool:
    a = addr.lower()
    return any(x in a for x in _EMAIL_DENY)


def extract(html: str) -> "dict[str, str]":
    out = {c: "" for c in COLUMNS}
    hrefs = [_html.unescape(m.group(1)).strip() for m in _A_HREF.finditer(html)]

    # Email: prefer an explicit mailto: link (the real contact), then fall back to
    # the first address that is NOT vendor/tooling boilerplate. Script/JSON-LD text
    # is kept on purpose — many sites expose the real business email only inside a
    # <script type="application/ld+json"> block — and the deny-list (Sentry DSN,
    # wixpress no-reply, image files, …) filters the junk instead.
    for h in hrefs:
        if h.lower().startswith("mailto:"):
            addr = h[7:].split("?")[0].strip()
            if _EMAIL.fullmatch(addr) and not _bad_email(addr):
                out["email"] = addr
                break
    if not out["email"]:
        text = _TAG.sub(" ", html)
        for m in _EMAIL.finditer(text):
            if not _bad_email(m.group(0)):
                out["email"] = m.group(0)
                break

    for col, domains, bad in _SOCIAL:
        for h in hrefs:
            host = _host(h)
            if not _in_domain(host, domains):
                continue
            p = urlparse(h if "//" in h else "https://" + h)
            segs = [s for s in p.path.split("/") if s]
            if not segs or segs[0].lower() in bad:
                continue
            if segs[0].lower() == "profile.php":  # a real FB page: keep ?id=
                mid = re.search(r"id=\d+", p.query)
                out[col] = "https://" + host + "/profile.php" + ("?" + mid.group(0) if mid else "")
            else:
                out[col] = "https://" + host + p.path.rstrip("/")
            break
    return out


def _normalize(u: str) -> "str | None":
    u = (u or "").strip()
    if not u:
        return None
    low = u.lower()
    if low.startswith(("mailto:", "tel:", "javascript:", "data:", "ftp:", "#")):
        return None
    if not re.match(r"^https?://", low):
        if "://" in u:  # some other scheme we don't fetch
            return None
        u = "https://" + u
    return u


def load_urls(path: "str | None") -> "list[str]":
    if not path:
        raw = list(URLS)
    elif path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            sys.exit("input CSV is empty")
        col = next((c for c in ("website", "url", "link", "Website", "URL") if c in rows[0]), None)
        if not col:
            sys.exit("input CSV needs a website/url/link column")
        raw = [(r.get(col) or "") for r in rows]
    else:
        with open(path, encoding="utf-8-sig") as f:
            raw = [ln for ln in f if not ln.lstrip().startswith("#")]
    seen: "set[str]" = set()
    out: "list[str]" = []
    for u in raw:
        n = _normalize(u)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _safe_cell(v: str) -> str:
    # CSV/formula-injection guard: the visited site controls these values; one must
    # not open as a formula in Excel/Sheets.
    v = str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


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
        sys.exit("No usable URLs. Fill in URLS[] or pass --input.")

    fields = ["website"] + COLUMNS + ["status"]
    any_hit = 0
    counts = {c: 0 for c in COLUMNS}
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for i, url in enumerate(urls, 1):
            row = {c: "" for c in fields}
            row["website"] = url
            try:
                data = extract(fetch_html(url))
                row.update(data)
                hits = [c for c in COLUMNS if data.get(c)]
                for c in hits:
                    counts[c] += 1
                if hits:
                    any_hit += 1
                row["status"] = "ok (" + ",".join(h.split("_")[0] for h in hits) + ")" if hits else "no links found"
            except Exception as e:  # noqa: BLE001
                line = (str(e).strip().splitlines() or ["error"])[-1]
                row["status"] = "error: " + line[:70]
            w.writerow([_safe_cell(row[c]) for c in fields])
            f.flush()  # persist so a kill mid-batch keeps the rows written so far
            print(f"[{i}/{len(urls)}] {(_host(url) or url)[:34]:34} -> {row['status']}", file=sys.stderr)
            time.sleep(args.sleep)

    summary = ", ".join(f"{c.split('_')[0]} {counts[c]}" for c in COLUMNS)
    print(f"done: {any_hit}/{len(urls)} sites yielded a link ({summary}) -> {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
