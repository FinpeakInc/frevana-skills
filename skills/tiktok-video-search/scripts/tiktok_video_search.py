#!/usr/bin/env python3
"""TikTok public video search by keyword, hashtag, or username through Frevana (stdlib only)."""
import argparse
import getpass
import http.client
import json
import math
import os
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

API_ROOT = "/service/tiktok-videos/tasks"
DEFAULT_TIMEOUT = 21600
MAX_RESPONSE_BYTES = 52 * 1024 * 1024
SORTS = ['MOST_RELEVANT', 'MOST_LIKED', 'LATEST']
DATES = ['ALL_TIME', 'PAST_24_HOURS', 'PAST_WEEK', 'PAST_MONTH', 'LAST_3_MONTHS', 'LAST_6_MONTHS']
SUBTITLES = ['NEVER_DOWNLOAD_SUBTITLES', 'DOWNLOAD_SUBTITLES', 'DOWNLOAD_AND_TRANSCRIBE_VIDEOS_WITHOUT_SUBTITLES', 'TRANSCRIBE_ALL_VIDEOS']
PROXY_COUNTRIES = ['None', 'AF', 'AL', 'DZ', 'AS', 'AD', 'AO', 'AI', 'AG', 'AR', 'AM', 'AU', 'AT', 'AZ', 'BS', 'BH', 'BB', 'BY', 'BE', 'BZ', 'BJ', 'BM', 'BT', 'BO', 'BA', 'BW', 'BR', 'VG', 'BN', 'BG', 'BF', 'BI', 'KH', 'CM', 'CA', 'CV', 'KY', 'TD', 'CL', 'CO', 'CK', 'CR', 'HR', 'CY', 'CZ', 'CD', 'DK', 'DJ', 'DO', 'EC', 'EG', 'SV', 'EE', 'ET', 'FK', 'FJ', 'FI', 'FR', 'PF', 'GA', 'GE', 'DE', 'GH', 'GI', 'GR', 'GL', 'GD', 'GP', 'GT', 'GN', 'GW', 'GY', 'HN', 'HU', 'IS', 'ID', 'IQ', 'IE', 'IM', 'IL', 'IT', 'CI', 'JM', 'JP', 'JE', 'KZ', 'KE', 'XK', 'KW', 'LA', 'LV', 'LB', 'LS', 'LR', 'LY', 'LT', 'LU', 'MO', 'MG', 'MW', 'MY', 'MV', 'ML', 'MT', 'MH', 'MQ', 'MR', 'MU', 'MX', 'MD', 'MC', 'MN', 'ME', 'MA', 'MZ', 'MM', 'NA', 'NR', 'NP', 'NL', 'NZ', 'NI', 'NG', 'MK', 'NO', 'OM', 'PS', 'PA', 'PG', 'PY', 'PE', 'PH', 'PL', 'PT', 'PR', 'QA', 'CG', 'RO', 'RU', 'RW', 'RE', 'KN', 'LC', 'MF', 'PM', 'VC', 'SM', 'SA', 'SN', 'RS', 'SL', 'SG', 'SX', 'SK', 'SB', 'SO', 'ZA', 'KR', 'ES', 'LK', 'SR', 'SZ', 'SE', 'CH', 'TW', 'TJ', 'TZ', 'TH', 'TG', 'TO', 'TT', 'TN', 'TR', 'TC', 'TV', 'VI', 'UG', 'UA', 'AE', 'GB', 'US', 'UY', 'VE', 'VN', 'WF', 'YE', 'ZM', 'ZW', 'AX']
BOOL_FIELDS = ("should_download_covers",
               "should_download_slideshow_images", "should_download_avatars",
               "should_download_music_covers", "scrape_related_search_words",
               "scrape_additional_author_meta")
INT_BOUNDS = {"results_per_page": (1, 100), "least_diggs": (1, 9007199254740991),
              "most_diggs": (1, 9007199254740991), "comments_per_post": (0, 1000),
              "top_level_comments_per_post": (0, 1000), "max_replies_per_comment": (0, 100)}
SEARCH_FIELDS = ("search_queries", "hashtags", "profiles", "video_search_sorting", "video_search_date_filter",
                 "download_subtitles_options", "proxy_country_code",
                 "video_kv_store_id_or_name", "max_total_charge_usd", *BOOL_FIELDS, *INT_BOUNDS)
TERMINAL_FAILURES = {"FAILED", "REVIEW_REQUIRED", "RESULT_EXPIRED"}


class CliError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def boolean(value):
    if value not in ("true", "false"):
        raise argparse.ArgumentTypeError("use true or false")
    return value == "true"


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("create", "status", "result", "items", "wait", "run"))
    p.add_argument("--query", "--keyword", dest="search_queries", action="append",
                   help="Repeat for 1-5 video search keywords, each 1-256 characters.")
    p.add_argument("--hashtag", dest="hashtags", action="append", help="Repeat for 1-5 hashtags without #; up to 128 characters each.")
    p.add_argument("--username", dest="profiles", action="append", help="Repeat for 1-5 usernames without @; up to 128 characters each.")
    p.add_argument("--video-search-sorting", choices=SORTS, help="Default MOST_RELEVANT; nondefault sorting costs extra.")
    p.add_argument("--video-search-date-filter", choices=DATES, help="Default ALL_TIME; date filtering costs extra.")
    for field in INT_BOUNDS:
        p.add_argument("--" + field.replace("_", "-"), type=int, help=f"Range {INT_BOUNDS[field]}." + (" Maximum videos per keyword, hashtag, or username; default 20." if field == "results_per_page" else ""))
    for field in BOOL_FIELDS:
        p.add_argument("--" + field.replace("_", "-"), type=boolean, metavar="true|false",
                       help="Default false; enable only when requested.")
    p.add_argument("--download-subtitles-options", choices=SUBTITLES)
    p.add_argument("--proxy-country-code", choices=PROXY_COUNTRIES, help="Proxy exit location, not author country; default None.")
    p.add_argument("--video-kv-store-id-or-name", help="User-scoped storage alias: 1-63 letters, digits or hyphens.")
    p.add_argument("--max-total-charge-usd", type=str, help="Upstream Run budget: 0.50-1000 USD, at most 2 decimal places.")
    p.add_argument("--offset", type=int, help="items only; default 0.")
    p.add_argument("--limit", type=int, help="items only; 1-1000, default 100.")
    p.add_argument("--client-task-id", help="Stable idempotency ID, up to 128 characters.")
    p.add_argument("--task-id", help="UUID v4 returned by create.")
    p.add_argument("--wait", action="store_true", help="Wait after create; same as run.")
    p.add_argument("--timeout", type=int, default=None, help="Wait budget in seconds; default 21600, 0 disables it.")
    p.add_argument("--output", help="Save unchanged JSON; run/wait save under ./out/ by default.")
    p.add_argument("--token", help="One-time Frevana bearer token override.")
    p.add_argument("--api-key", help="One-time Frevana API key override.")
    p.add_argument("--api-base-url", default=os.environ.get("FREVANA_API_BASE_URL", "https://ai-factory.frevana.com"))
    return p


def validate_task_id(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}", value
    ):
        raise CliError("task_id must be a UUID v4")
    return str(uuid.UUID(value))


def validate_args(args):
    if args.token and args.api_key:
        raise CliError("choose --token or --api-key")
    if args.action != "items" and (args.offset is not None or args.limit is not None):
        raise CliError("--offset and --limit require items")
    if args.offset is not None and args.offset < 0:
        raise CliError("--offset must be nonnegative")
    if args.limit is not None and not 1 <= args.limit <= 1000:
        raise CliError("--limit must be between 1 and 1000")
    creates = args.action in ("create", "run")
    waits = args.action in ("wait", "run") or (args.action == "create" and args.wait)
    if creates:
        if args.task_id is not None:
            raise CliError(f"--task-id is not valid with {args.action}")
    else:
        args.task_id = validate_task_id(args.task_id)
        if args.client_task_id is not None or any(
            getattr(args, field) is not None for field in SEARCH_FIELDS
        ):
            raise CliError(f"creation options are not valid with {args.action}")
    if args.wait and args.action != "create":
        raise CliError("--wait is valid only with create")
    if args.timeout is not None and (args.timeout < 0 or not waits):
        raise CliError("--timeout must be nonnegative and requires wait, run, or create --wait")


def trimmed(value, field, maximum):
    value = value.strip()
    if not value or len(value) > maximum:
        raise CliError(f"{field} must contain 1-{maximum} characters after trimming")
    return value


def create_payload(args):
    payload = {"client_task_id": trimmed(args.client_task_id if args.client_task_id is not None
                                          else str(uuid.uuid4()), "client_task_id", 128)}
    supplied = {field: getattr(args, field) for field in SEARCH_FIELDS if getattr(args, field) is not None}
    supplied.setdefault("results_per_page", 20)
    sources = [field for field in ("search_queries", "hashtags", "profiles") if field in supplied]
    if len(sources) != 1:
        raise CliError("choose exactly one source: --query, --hashtag, or --username")
    source = sources[0]
    entries = supplied[source]
    maximum = 256 if source == "search_queries" else 128
    if not 1 <= len(entries) <= 5:
        raise CliError("provide 1-5 values of the selected source type")
    if any(len(entry) > maximum for entry in entries):
        raise CliError(f"{source} entries must not exceed {maximum} characters")
    entries = [trimmed(entry, source, maximum) for entry in entries]
    if source == "profiles" and any(not re.fullmatch(r"[A-Za-z0-9_.]{1,128}", entry) for entry in entries):
        raise CliError("provide usernames without @, not profile URLs")
    if source == "hashtags" and any(not re.fullmatch(r"[^\s#/?]+", entry) for entry in entries):
        raise CliError("provide hashtags without #, whitespace, / or ?")
    supplied[source] = sorted(set(entries))
    if source == "search_queries":
        supplied["search_section"] = "/video"
    elif any(field in supplied for field in ("video_search_sorting", "video_search_date_filter", "scrape_related_search_words")):
        raise CliError("video search sorting/date filters and related search words require --query")
    for field, (low, high) in INT_BOUNDS.items():
        if field in supplied and not low <= supplied[field] <= high:
            raise CliError(f"{field} must be between {low} and {high}")
    if supplied.get("video_search_date_filter", "ALL_TIME") != "ALL_TIME" and any(
            key in supplied for key in ("most_diggs", "least_diggs")):
        raise CliError("date filters cannot be combined with like-count filters")
    if ("least_diggs" in supplied and "most_diggs" in supplied
            and supplied["least_diggs"] >= supplied["most_diggs"]):
        raise CliError("least_diggs must be less than most_diggs")
    comments = supplied.get("comments_per_post", 0)
    if not comments and (supplied.get("top_level_comments_per_post", 0) or supplied.get("max_replies_per_comment", 0)):
        raise CliError("comment limits require comments_per_post > 0")
    if supplied.get("top_level_comments_per_post", 0) > comments:
        raise CliError("top_level_comments_per_post cannot exceed comments_per_post")
    if "video_kv_store_id_or_name" in supplied and not re.fullmatch(r"[A-Za-z0-9-]{1,63}", supplied["video_kv_store_id_or_name"]):
        raise CliError("invalid storage alias")
    if "max_total_charge_usd" in supplied:
        from decimal import Decimal, InvalidOperation
        try:
            amount = Decimal(supplied["max_total_charge_usd"])
            if not amount.is_finite() or not Decimal("0.5") <= amount <= 1000 or amount != amount.quantize(Decimal("0.01")):
                raise ValueError()
        except (InvalidOperation, ValueError) as exc:
            raise CliError("budget must be 0.50-1000 USD with at most 2 decimal places") from exc
        supplied["max_total_charge_usd"] = float(amount)
    return {**payload, **supplied}


def validate_base_url(value):
    parsed = urllib.parse.urlsplit(value)
    try:
        parsed.port
    except ValueError as exc:
        raise CliError("invalid API base URL port") from exc
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or any(c.isspace() for c in value)):
        raise CliError("API base URL must be HTTP(S), without credentials, query, or fragment")
    return value.rstrip("/")


class Client:
    def __init__(self, base_url, headers):
        self.base_url = validate_base_url(base_url)
        self.headers = headers
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, suffix="", payload=None, timeout=600):
        # A socket timeout limits inactivity, not total time. Keep network work
        # separate from output so a slow header/body cannot outlive this budget
        # and then write a successful result. Daemon workers never emit files.
        deadline = time.monotonic() + timeout
        completed = queue.Queue(maxsize=1)
        cancelled = threading.Event()

        def perform():
            try:
                raw = self._request(method, suffix, payload, timeout, cancelled)
                completed.put((raw, None))
            except Exception as exc:
                completed.put((None, exc))

        threading.Thread(target=perform, daemon=True).start()
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise queue.Empty()
            raw, error = completed.get(timeout=remaining)
            if time.monotonic() >= deadline:
                raise queue.Empty()
            if error is not None:
                raise error
            return raw
        except queue.Empty as exc:
            raise CliError("Frevana API request timed out; resume wait with the existing task ID") from exc
        finally:
            cancelled.set()

    def _request(self, method, suffix, payload, timeout, cancelled):
        headers = {**self.headers, "Accept": "application/json"}
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + API_ROOT + suffix,
                                     data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as response:
                chunks = []
                total = 0
                while not cancelled.is_set():
                    chunk = response.read1(min(64 * 1024, MAX_RESPONSE_BYTES + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise CliError("response exceeds the 52 MiB client limit")
                    chunks.append(chunk)
                if cancelled.is_set():
                    raise CliError("Frevana API request cancelled after timeout")
                raw = b"".join(chunks)
                if response.length is not None and response.length > 0:
                    raise http.client.IncompleteRead(raw, response.length)
                if not raw:
                    raise CliError("API returned an empty response")
                return raw
        except urllib.error.HTTPError as exc:
            detail = exc.read(65536).decode("utf-8", errors="replace")
            exc.close()
            raise CliError(f"Frevana API HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
            raise CliError(f"Frevana API transport failed: {exc}") from exc


def decode_json(raw):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CliError("API returned invalid JSON") from exc


def read_task(raw):
    task = decode_json(raw)
    if not isinstance(task, dict):
        raise CliError("API did not return a task object")
    validate_task_id(task.get("task_id"))
    if task.get("status") not in {"PENDING", "RUNNING", "SETTLING", "READY", *TERMINAL_FAILURES}:
        raise CliError("API returned an unknown task status")
    if not isinstance(task.get("result_available"), bool):
        raise CliError("API task is missing result_available")
    return task


def check_terminal(task):
    if task["status"] in TERMINAL_FAILURES:
        raise CliError(f"Task {task['task_id']} ended with {task['status']}: "
                       f"{task.get('error_code') or ''} {task.get('error_message') or ''}".rstrip())


def emit(raw, output=None):
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        print(f"Saved TikTok video JSON to {destination}", file=sys.stderr)
    sys.stdout.buffer.write(raw)


def fetch_result(client, task_id, output, timeout=600):
    deadline = time.monotonic() + timeout
    raw = client.request("GET", f"/{task_id}/result", timeout=timeout)
    if not isinstance(decode_json(raw), list):
        raise CliError("Result endpoint did not return a JSON array")
    if time.monotonic() >= deadline:
        raise CliError("Timed out retrieving result; resume wait with the existing task ID")
    emit(raw, output)


def default_output():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"out/tiktok-video-search-result-{stamp}-{uuid.uuid4().hex[:8]}.json"


def wait_for_result(client, task_id, timeout, output, initial=None):
    task_id = validate_task_id(task_id)
    deadline = time.monotonic() + timeout if timeout else None
    task = initial
    last_status = None

    def request_timeout():
        remaining = deadline - time.monotonic() if deadline is not None else 600
        if remaining <= 0:
            raise CliError(f"Timed out waiting for task {task_id}; resume with wait --task-id {task_id}")
        return min(600, remaining)

    while True:
        if task is None:
            task = read_task(client.request("GET", f"/{task_id}", timeout=request_timeout()))
        if validate_task_id(task["task_id"]) != task_id:
            raise CliError("API returned a different task_id")
        check_terminal(task)
        if task["status"] != last_status:
            print(f"TikTok video task {task_id}: {task['status']}", file=sys.stderr)
            last_status = task["status"]
        if task["status"] == "READY" and task["result_available"]:
            fetch_result(client, task_id, output or default_output(), request_timeout())
            return
        delay = task.get("next_poll_after_ms")
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not math.isfinite(delay) or delay < 0:
            raise CliError("API task has invalid next_poll_after_ms")
        if delay == 0:
            raise CliError(f"Task {task_id} has no available result and automatic polling must stop")
        remaining = max(0, deadline - time.monotonic()) if deadline is not None else None
        time.sleep(min(delay / 1000, remaining) if remaining is not None else delay / 1000)
        request_timeout()
        task = None


def auth_headers(args):
    token = args.token
    api_key = args.api_key
    if not token and not api_key:
        token = os.environ.get("FREVANA_TOKEN")
        if not token:
            api_key = os.environ.get("FREVANA_API_KEY")
    if not token and not api_key and sys.stdin.isatty():
        token = getpass.getpass("Enter Frevana bearer token: ")
    credential = token or api_key
    if not credential:
        raise CliError("Set FREVANA_TOKEN or FREVANA_API_KEY, or pass --token or --api-key")
    if any(ord(c) < 32 or ord(c) == 127 for c in credential):
        raise CliError("credential must not contain control characters")
    return {"Authorization": f"Bearer {token}"} if token else {"x-api-key": api_key}


def main():
    args = parser().parse_args()
    validate_args(args)
    payload = create_payload(args) if args.action in ("create", "run") else None
    client = Client(args.api_base_url, auth_headers(args))
    timeout = args.timeout if args.timeout is not None else DEFAULT_TIMEOUT
    if payload is not None:
        client_id = payload["client_task_id"]
        print(f"Using client_task_id: {client_id}", file=sys.stderr)
        try:
            raw = client.request("POST", payload=payload)
            task = read_task(raw)
        except CliError:
            print("Creation may have been accepted. Do not submit a new task automatically; "
                  f"retry only with identical options and --client-task-id {client_id}", file=sys.stderr)
            raise
        if args.action == "run" or args.wait:
            wait_for_result(client, task["task_id"], timeout, args.output, initial=task)
        else:
            emit(raw, args.output)
            check_terminal(task)
    elif args.action == "status":
        raw = client.request("GET", f"/{args.task_id}")
        read_task(raw)
        emit(raw, args.output)
    elif args.action == "items":
        query = urllib.parse.urlencode({"offset": args.offset if args.offset is not None else 0,
                                        "limit": args.limit if args.limit is not None else 100})
        raw = client.request("GET", f"/{args.task_id}/items?{query}")
        page = decode_json(raw)
        if (not isinstance(page, dict) or not isinstance(page.get("items"), list)
                or validate_task_id(page.get("task_id")) != args.task_id):
            raise CliError("API returned an invalid items page")
        emit(raw, args.output)
    elif args.action == "result":
        fetch_result(client, args.task_id, args.output)
    else:
        wait_for_result(client, args.task_id, timeout, args.output)


if __name__ == "__main__":
    try:
        main()
    except (CliError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted; resume using the existing task ID.", file=sys.stderr)
        sys.exit(130)
