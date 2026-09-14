#!/usr/bin/env python3
import argparse
import getpass
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

SKILL_NAME = "tiktok-posts-discover-by-profile-url"
OPERATION = "posts.discover_by_profile_url"
CREATE_PATH = "posts/discover-by-profile-url"
DEFAULT_API_BASE_URL = "https://ai-factory.frevana.com"
API_ROOT = "/service/tiktok"
POLL_INTERVAL_SECONDS = 10
DEFAULT_TIMEOUT_SECONDS = 21600
MAX_RESPONSE_BYTES = 52 * 1024 * 1024
TERMINAL_FAILURES = {"FAILED", "EXPIRED", "TRIGGER_UNKNOWN"}

class CliError(Exception):
    pass

class ApiError(CliError):
    def __init__(self, message, body=b""):
        super().__init__(message)
        self.body = body

def parser():
    result = argparse.ArgumentParser(
        description=f"Create, poll, and retrieve {OPERATION} tasks through Frevana."
    )
    result.add_argument("action", choices=("create", "status", "result", "wait", "run"))
    result.add_argument("--input-json", action="append", default=[],
                        help="One JSON input object; repeat for multiple inputs.")
    result.add_argument("--input-file", help="Path to a JSON array of input objects.")
    result.add_argument("--client-task-id")
    result.add_argument("--limit-per-input", type=int)
    result.add_argument("--task-id")
    result.add_argument("--wait", action="store_true", help="Wait after create.")
    result.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS,
                        help="Wait timeout in seconds; 0 disables it (default: 21600).")
    result.add_argument("--output")
    result.add_argument("--token")
    result.add_argument("--api-base-url",
                        default=os.environ.get("FREVANA_API_BASE_URL", DEFAULT_API_BASE_URL))
    return result

def require_string(value, field, maximum=None, allow_empty=False):
    if not isinstance(value, str):
        raise CliError(f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise CliError(f"{field} must not be empty")
    if maximum is not None and len(value) > maximum:
        raise CliError(f"{field} must not exceed {maximum} characters")

def require_nonnegative_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CliError(f"{field} must be an integer greater than or equal to 0")

def validate_tiktok_url(value, field, kind):
    require_string(value, field, 2048)
    parsed = urllib.parse.urlsplit(value.strip())
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise CliError(f"{field} must be a valid HTTPS TikTok {kind} URL") from exc
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or port not in (None, 443)
            or (host != "tiktok.com" and not host.endswith(".tiktok.com"))):
        raise CliError(f"{field} must be a valid HTTPS TikTok {kind} URL")
    path = parsed.path.rstrip("/")
    pattern = r"/@[^/]+/video/[0-9]+" if kind == "post" else r"/@[^/]+"
    if not re.fullmatch(pattern, path):
        raise CliError(f"{field} must be a valid HTTPS TikTok {kind} URL")
    return value.strip()

def parse_date(value, field):
    require_string(value, field, allow_empty=True)
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m-%d-%Y")
    except ValueError as exc:
        raise CliError(f"{field} must be a valid MM-DD-YYYY date") from exc

def validate_input(item, index):
    if not isinstance(item, dict):
        raise CliError(f"input[{index}] must be a JSON object")
    prefix = f"input[{index}]"
    output = dict(item)
    allowed = {"country"}
    if OPERATION == "posts.discover_by_keyword":
        allowed |= {"search_keyword", "num_of_posts"}
        require_string(item.get("search_keyword"), f"{prefix}.search_keyword", 256)
        if "num_of_posts" in item:
            require_nonnegative_int(item["num_of_posts"], f"{prefix}.num_of_posts")
    elif OPERATION == "posts.discover_by_profile_url":
        allowed |= {"url", "num_of_posts", "posts_to_not_include", "what_to_collect",
                    "start_date", "end_date", "post_type", "sort_by"}
        output["url"] = validate_tiktok_url(item.get("url"), f"{prefix}.url", "profile")
        if "num_of_posts" in item:
            require_nonnegative_int(item["num_of_posts"], f"{prefix}.num_of_posts")
        if "posts_to_not_include" in item:
            values = item["posts_to_not_include"]
            if not isinstance(values, list) or len(values) > 500:
                raise CliError(f"{prefix}.posts_to_not_include must be an array of at most 500 strings")
            if any(not isinstance(value, str) for value in values):
                raise CliError(f"{prefix}.posts_to_not_include must contain strings")
            if len(set(values)) != len(values):
                raise CliError(f"{prefix}.posts_to_not_include must contain unique strings")
            for value in values:
                require_string(value, f"{prefix}.posts_to_not_include[]", 128)
        if "what_to_collect" in item:
            require_string(item["what_to_collect"], f"{prefix}.what_to_collect", 128, True)
        start = parse_date(item.get("start_date", ""), f"{prefix}.start_date")
        end = parse_date(item.get("end_date", ""), f"{prefix}.end_date")
        if start and end and end <= start:
            raise CliError(f"{prefix}.end_date must be later than start_date")
        if "post_type" in item and item["post_type"] not in ("", "Video Posts", "Image Posts"):
            raise CliError(f'{prefix}.post_type must be "", "Video Posts", or "Image Posts"')
        if "sort_by" in item:
            require_string(item["sort_by"], f"{prefix}.sort_by", 64, True)
    elif OPERATION == "posts.collect_by_url":
        allowed.add("url")
        output["url"] = validate_tiktok_url(item.get("url"), f"{prefix}.url", "post")
    else:
        allowed.add("url")
        output["url"] = validate_tiktok_url(item.get("url"), f"{prefix}.url", "profile")
    unsupported = sorted(set(item) - allowed)
    if unsupported:
        raise CliError(f"{prefix} contains unsupported fields: {', '.join(unsupported)}")
    if "country" in item:
        country = item["country"]
        require_string(country, f"{prefix}.country", allow_empty=True)
        if country and not re.fullmatch(r"[A-Za-z]{2}", country):
            raise CliError(f"{prefix}.country must be an ISO 3166-1 alpha-2 code or empty")
        output["country"] = country.upper()
    return output

def load_inputs(args):
    if args.input_file and args.input_json:
        raise CliError("use only one of --input-file or --input-json")
    if args.input_file:
        try:
            values = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CliError(f"could not read --input-file as JSON: {exc}") from exc
    else:
        values = []
        for raw in args.input_json:
            try:
                values.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise CliError(f"invalid --input-json: {exc}") from exc
    if not isinstance(values, list) or not 1 <= len(values) <= 20:
        raise CliError("provide between 1 and 20 input objects")
    return [validate_input(value, index) for index, value in enumerate(values)]

def validate_base_url(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc
            or parsed.query or parsed.fragment):
        raise CliError("--api-base-url must be an HTTP(S) base URL without query or fragment")
    return value.rstrip("/")

class Client:
    def __init__(self, base_url, token):
        self.base_url = validate_base_url(base_url)
        self.token = token

    def request(self, method, path, payload=None):
        body = None
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{API_ROOT}/{path.lstrip('/')}",
            data=body, headers=headers, method=method
        )
        handle = tempfile.NamedTemporaryFile(prefix=f"{SKILL_NAME}-", suffix=".json", delete=False)
        temp_path = Path(handle.name)
        succeeded = False
        try:
            with handle, urllib.request.urlopen(request, timeout=600) as response:
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise CliError("response exceeds the 52 MiB client safety limit")
                    handle.write(chunk)
                if not total:
                    raise CliError("Frevana TikTok API returned an empty response")
                succeeded = True
                return temp_path
        except urllib.error.HTTPError as exc:
            raise ApiError(f"Frevana TikTok API request failed with HTTP {exc.code}",
                           exc.read(MAX_RESPONSE_BYTES)) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ApiError(f"Frevana TikTok API transport failed: {exc}") from exc
        finally:
            if not succeeded:
                temp_path.unlink(missing_ok=True)

def read_task(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliError(f"API returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CliError("API returned a snapshot where a task object was expected")
    return value

def emit(path, output=None):
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        print(f"Saved TikTok JSON to {destination}", file=sys.stderr)
    with path.open("rb") as source:
        shutil.copyfileobj(source, sys.stdout.buffer)

def default_output():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"out/{SKILL_NAME}-result-{stamp}-{os.getpid()}.json"

def check_terminal(task):
    status = task.get("status")
    if status in TERMINAL_FAILURES:
        detail = task.get("error_message") or "no error detail"
        task_id = task.get("task_id")
        label = f"TikTok task {task_id}" if task_id else "TikTok task"
        raise CliError(f"{label} ended with {status}: {detail}")

def wait_for_result(client, task_id, timeout, output):
    started = time.monotonic()
    last_state = None
    while True:
        status_path = client.request("GET", f"tasks/{task_id}")
        try:
            task = read_task(status_path)
            check_terminal(task)
            state = (task.get("status"), task.get("billing_status"))
            if state != last_state:
                print(
                    f"TikTok task {task_id}: status={state[0]}, "
                    f"billing_status={state[1]}",
                    file=sys.stderr,
                )
                last_state = state
            if task.get("status") == "READY" and task.get("billing_status") == "BILLED":
                result_path = client.request("GET", f"tasks/{task_id}/result")
                try:
                    with result_path.open("rb") as result_file:
                        first = result_file.read(4096).lstrip()[:1]
                    if first == b"[":
                        emit(result_path, output or default_output())
                        return
                    check_terminal(read_task(result_path))
                finally:
                    result_path.unlink(missing_ok=True)
            if timeout and time.monotonic() - started >= timeout:
                raise CliError(f"timed out waiting for TikTok task {task_id}")
            time.sleep(POLL_INTERVAL_SECONDS)
        finally:
            status_path.unlink(missing_ok=True)

def validate_args(args):
    creates = args.action in ("create", "run")
    if creates:
        if args.task_id:
            raise CliError(f"--task-id is not valid with {args.action}")
    else:
        if not args.task_id:
            raise CliError(f"{args.action} requires --task-id")
        try:
            parsed = uuid.UUID(args.task_id)
        except ValueError as exc:
            raise CliError("--task-id must be a UUID v4") from exc
        if parsed.version != 4:
            raise CliError("--task-id must be a UUID v4")
        if args.input_file or args.input_json or args.client_task_id or args.limit_per_input is not None:
            raise CliError(f"creation options are not valid with {args.action}")
    if args.wait and args.action != "create":
        raise CliError("--wait is valid only with create")
    if args.timeout < 0:
        raise CliError("--timeout must be 0 or greater")
    waits = args.action in ("wait", "run") or (args.action == "create" and args.wait)
    if not waits and args.timeout != DEFAULT_TIMEOUT_SECONDS:
        raise CliError("--timeout is valid only with wait, run, or create --wait")

def create_payload(args):
    client_task_id = args.client_task_id or str(uuid.uuid4())
    require_string(client_task_id, "--client-task-id", 128)
    if args.limit_per_input is not None and not 1 <= args.limit_per_input <= 2147483647:
        raise CliError("--limit-per-input must be between 1 and 2147483647")
    payload = {"client_task_id": client_task_id, "input": load_inputs(args)}
    if args.limit_per_input is not None:
        payload["limit_per_input"] = args.limit_per_input
    if len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()) > 1024 * 1024:
        raise CliError("TikTok task request exceeds 1 MB")
    return client_task_id, payload

def main():
    args = parser().parse_args()
    validate_args(args)
    token = args.token or os.environ.get("FREVANA_TOKEN", "")
    if not token and sys.stdin.isatty():
        token = getpass.getpass("FREVANA_TOKEN not found. Enter Frevana bearer token: ")
    if not token:
        raise CliError("FREVANA_TOKEN is not set; set it or pass --token")
    client = Client(args.api_base_url, token)

    if args.action in ("create", "run"):
        client_task_id, payload = create_payload(args)
        print(f"Using client_task_id: {client_task_id}", file=sys.stderr)
        try:
            response_path = client.request("POST", CREATE_PATH, payload)
        except ApiError as exc:
            if not exc.body:
                print("Creation outcome may be unknown. Do not submit a new task; "
                      f"retry with --client-task-id {client_task_id}", file=sys.stderr)
            raise
        try:
            task = read_task(response_path)
            task_id = task.get("task_id")
            if not isinstance(task_id, str):
                raise CliError("create response is missing task_id")
            if args.action == "run" or args.wait:
                check_terminal(task)
                print(f"Created TikTok task {task_id}; waiting for raw result", file=sys.stderr)
                wait_for_result(client, task_id, args.timeout, args.output)
            else:
                emit(response_path, args.output)
                check_terminal(task)
        finally:
            response_path.unlink(missing_ok=True)
    elif args.action == "status":
        path = client.request("GET", f"tasks/{args.task_id}")
        try:
            read_task(path)
            emit(path, args.output)
        finally:
            path.unlink(missing_ok=True)
    elif args.action == "result":
        path = client.request("GET", f"tasks/{args.task_id}/result")
        try:
            emit(path, args.output)
        finally:
            path.unlink(missing_ok=True)
    else:
        wait_for_result(client, args.task_id, args.timeout, args.output)

if __name__ == "__main__":
    try:
        main()
    except ApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if exc.body:
            try:
                print(exc.body.decode("utf-8"), file=sys.stderr)
            except UnicodeDecodeError:
                print("API returned a non-text error body", file=sys.stderr)
        sys.exit(1)
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
