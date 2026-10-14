#!/usr/bin/env python3
"""TikTok Ads Library asynchronous search through Frevana (stdlib only)."""
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
from datetime import date, datetime, timezone
from pathlib import Path

API_ROOT = "/apify/tiktok-ads/tasks"
DEFAULT_TIMEOUT = 21600
MAX_RESPONSE_BYTES = 52 * 1024 * 1024
COUNTRIES = "all FR AT BE BG HR CY CZ DK EE FI DE GR HU IS IE IT LV LI LT LU MT NL NO PL PT RO SK SI ES SE CH GB".split()
SORTS = [f"{field},{order}" for field in ("last_shown_date", "create_time", "impression")
         for order in ("desc", "asc")]
SEARCH_FIELDS = ("query", "advertiser_name", "max_pages", "start_date", "end_date",
                 "timezone", "country", "sort_by", "quick_search")
TERMINAL_FAILURES = {"FAILED", "REVIEW_REQUIRED", "RESULT_EXPIRED"}


class CliError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("create", "status", "result", "wait", "run"))
    p.add_argument("--query")
    p.add_argument("--advertiser-name")
    p.add_argument("--ad-id", dest="ad_ids", action="append", default=[],
                   help="Repeat for 1-100 unique numeric ad IDs; excludes all search filters.")
    p.add_argument("--max-pages", type=int, help="1-25; server default 1 (12 ads per page).")
    p.add_argument("--start-date", help="YYYY-MM-DD; server default one year ago (UTC).")
    p.add_argument("--end-date", help="YYYY-MM-DD; server default today (UTC).")
    p.add_argument("--timezone", help="Actor-supported timezone; server default UTC.")
    p.add_argument("--country", choices=COUNTRIES, help="Server default all.")
    p.add_argument("--sort-by", choices=SORTS)
    p.add_argument("--quick-search", choices=("true", "false"),
                   help="Skip detailed enrichment when true; server default false.")
    p.add_argument("--client-task-id", help="Stable idempotency ID, up to 128 characters.")
    p.add_argument("--task-id", help="UUID v4 returned by create.")
    p.add_argument("--wait", action="store_true", help="Wait after create; same as run.")
    p.add_argument("--timeout", type=int, default=None,
                   help="Wait budget in seconds; default 21600, 0 disables it.")
    p.add_argument("--output", help="Save unchanged JSON; run/wait save under ./out/ by default.")
    auth = p.add_mutually_exclusive_group()
    auth.add_argument("--token", help="One-time Frevana JWT override.")
    auth.add_argument("--api-key", help="One-time Frevana API key override.")
    p.add_argument("--api-base-url", default=os.environ.get(
        "FREVANA_API_BASE_URL", "https://ai-factory.frevana.com"))
    return p


def validate_task_id(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}", value
    ):
        raise CliError("task_id must be a UUID v4")
    return str(uuid.UUID(value))


def validate_args(args):
    creates = args.action in ("create", "run")
    waits = args.action in ("wait", "run") or (args.action == "create" and args.wait)
    if creates:
        if args.task_id is not None:
            raise CliError(f"--task-id is not valid with {args.action}")
    else:
        args.task_id = validate_task_id(args.task_id)
        if args.ad_ids or args.client_task_id is not None or any(
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
    payload = {"client_task_id": trimmed(
        args.client_task_id if args.client_task_id is not None else str(uuid.uuid4()),
        "client_task_id", 128)}
    supplied = {field: getattr(args, field) for field in SEARCH_FIELDS
                if getattr(args, field) is not None}
    if args.ad_ids:
        if supplied:
            raise CliError("--ad-id cannot be combined with search parameters")
        if not 1 <= len(args.ad_ids) <= 100 or len(set(args.ad_ids)) != len(args.ad_ids):
            raise CliError("provide 1-100 unique ad IDs")
        if any(not re.fullmatch(r"[0-9]{1,32}", value) for value in args.ad_ids):
            raise CliError("each ad ID must be a string of 1-32 digits")
        return {**payload, "ad_ids": args.ad_ids}
    for field in ("query", "advertiser_name"):
        if field in supplied:
            supplied[field] = trimmed(supplied[field], field, 256)
    if not (supplied.get("query") or supplied.get("advertiser_name")) and supplied.get("country", "all") == "all":
        raise CliError("provide --query, --advertiser-name, a specific --country, or --ad-id")
    if "max_pages" in supplied and not 1 <= supplied["max_pages"] <= 25:
        raise CliError("--max-pages must be between 1 and 25")
    if "timezone" in supplied:
        zones = json.loads((Path(__file__).resolve().parents[1] / "references/timezones.json").read_text())
        if supplied["timezone"] not in zones:
            raise CliError("--timezone is not supported by the Actor; see references/timezones.json")
    for field in ("start_date", "end_date"):
        if field in supplied:
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", supplied[field]):
                    raise ValueError()
                date.fromisoformat(supplied[field])
            except ValueError as exc:
                raise CliError(f"{field} must be a valid YYYY-MM-DD date") from exc
    if supplied.get("start_date") and supplied.get("end_date") and supplied["start_date"] > supplied["end_date"]:
        raise CliError("--start-date must not be later than --end-date")
    # Leave omitted dates to the server so retries preserve identical logical inputs.
    if "quick_search" in supplied:
        supplied["quick_search"] = supplied["quick_search"] == "true"
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
        print(f"Saved TikTok Ads JSON to {destination}", file=sys.stderr)
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
    return f"out/tiktok-ads-search-result-{stamp}-{uuid.uuid4().hex[:8]}.json"


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
            print(f"TikTok Ads task {task_id}: {task['status']}", file=sys.stderr)
            last_status = task["status"]
        if task["status"] == "READY" and task["result_available"]:
            fetch_result(client, task_id, output or default_output(), request_timeout())
            return
        delay = task.get("next_poll_after_ms")
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not math.isfinite(delay) or delay < 0:
            raise CliError("API task has invalid next_poll_after_ms")
        if delay == 0:
            raise CliError(f"Task {task_id} has no available result and automatic polling must stop")
        remaining = request_timeout() if deadline is not None else None
        time.sleep(min(delay / 1000, remaining) if remaining is not None else delay / 1000)
        request_timeout()
        task = None


def auth_headers(args):
    token = args.token
    api_key = args.api_key
    if token is None and api_key is None:
        token = os.environ.get("FREVANA_TOKEN")
        if not token:
            api_key = os.environ.get("FREVANA_API_KEY")
    if not token and not api_key and sys.stdin.isatty():
        token = getpass.getpass("Enter Frevana bearer token: ")
    secret = token or api_key
    if not secret:
        raise CliError("set FREVANA_TOKEN or FREVANA_API_KEY, or pass --token/--api-key")
    if any(ord(c) < 32 or ord(c) == 127 for c in secret):
        raise CliError("credential must not contain control characters")
    return {"Authorization": f"Bearer {token}"} if token else {"X-API-Key": api_key}


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
