#!/usr/bin/env python3
"""Read-only AppsFlyer Master and Aggregate Pull reporting CLI."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

DEFAULT_API_BASE_URL = "https://hq1.appsflyer.com"
DEFAULT_TIMEOUT = 60
MAX_ATTEMPTS = 4
MAX_CHUNK_DAYS = 31
USER_AGENT = "frevana-appsflyer-reporting-skill/1"

PULL_REPORT_PATHS = {
    "partners": "partners_report",
    "partners-daily": "partners_by_date_report",
    "daily": "daily_report",
    "geo": "geo_report",
    "geo-daily": "geo_by_date_report",
}
DAILY_PULL_REPORTS = {"partners-daily", "daily", "geo-daily"}


class CliError(Exception):
    """Expected failure that is safe to show to the user."""


class ApiResponse:
    def __init__(self, body: bytes, content_type: str = "") -> None:
        self.body = body
        self.content_type = content_type


def iso_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must use YYYY-MM-DD") from exc
    return value


def comma_values(value: str) -> list[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("must include at least one value")
    return values


def calculated_kpi(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("must use calculated_kpi_name=formula")
    name, formula = (part.strip() for part in value.split("=", 1))
    if not name.startswith("calculated_kpi_") or not formula:
        raise argparse.ArgumentTypeError(
            "name must start with calculated_kpi_ and formula must not be empty"
        )
    return name, formula


def validate_date_range(start: str, end: str) -> None:
    if dt.date.fromisoformat(start) > dt.date.fromisoformat(end):
        raise CliError("--from must not be after --to")


def date_span_days(start: str, end: str) -> int:
    validate_date_range(start, end)
    return (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days + 1


def validate_master_date_range(start: str, end: str) -> None:
    if date_span_days(start, end) > MAX_CHUNK_DAYS:
        raise CliError(
            "Master API supports at most 31 inclusive days per report. "
            "Narrow --from/--to or run separate reports; aggregated chunks cannot be safely merged."
        )


def date_chunks(start: str, end: str, days: int = MAX_CHUNK_DAYS) -> list[tuple[str, str]]:
    validate_date_range(start, end)
    if days < 1:
        raise CliError("chunk size must be at least one day")
    current = dt.date.fromisoformat(start)
    final = dt.date.fromisoformat(end)
    chunks: list[tuple[str, str]] = []
    while current <= final:
        chunk_end = min(current + dt.timedelta(days=days - 1), final)
        chunks.append((current.isoformat(), chunk_end.isoformat()))
        current = chunk_end + dt.timedelta(days=1)
    return chunks


def api_base_url() -> str:
    base = os.environ.get("APPSFLYER_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
    parsed = urlparse(base)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise CliError("APPSFLYER_API_BASE_URL must be an HTTPS origin")
    return base


def auth_token() -> str:
    token = os.environ.get("APPSFLYER_API_TOKEN", "").strip()
    if not token:
        raise CliError("APPSFLYER_API_TOKEN is not set")
    return token


def redact(text: str, secrets: Iterable[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def response_content_type(response: Any) -> str:
    headers = getattr(response, "headers", None)
    if headers is None:
        return ""
    getter = getattr(headers, "get_content_type", None)
    if callable(getter):
        return str(getter())
    value = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
    return str(value).split(";", 1)[0].strip().lower()


def retry_delay(exc: HTTPError, attempt: int) -> float:
    retry_after = exc.headers.get("Retry-After") if exc.headers else None
    if retry_after:
        try:
            return min(float(retry_after), 30.0)
        except ValueError:
            pass
    return min(float(2**attempt), 30.0)


def request_api(
    endpoint: str,
    params: dict[str, Any] | None = None,
    *,
    accept: str,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
    timeout: int = DEFAULT_TIMEOUT,
    max_attempts: int = MAX_ATTEMPTS,
) -> ApiResponse:
    token = auth_token()
    query = urlencode(params or {}, doseq=True)
    url = f"{api_base_url()}{endpoint}"
    if query:
        url = f"{url}?{query}"
    request = Request(
        url,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )

    for attempt in range(max_attempts):
        try:
            with opener(request, timeout=timeout) as response:
                return ApiResponse(response.read(), response_content_type(response))
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if retryable and attempt + 1 < max_attempts:
                sleeper(retry_delay(exc, attempt))
                continue
            detail = exc.read(4096).decode("utf-8", errors="replace").strip()
            detail = redact(detail, [token])
            message = f"AppsFlyer API returned HTTP {exc.code} for {endpoint}"
            if detail:
                message += f": {detail}"
            if exc.code == 401:
                message += (
                    ". Check account access and regenerate API V2 tokens created before "
                    "2026-03-10 19:00 UTC"
                )
            raise CliError(message) from None
        except URLError as exc:
            reason = redact(str(exc.reason), [token])
            raise CliError(f"AppsFlyer API request failed for {endpoint}: {reason}") from None
        except TimeoutError:
            raise CliError(f"AppsFlyer API request timed out for {endpoint}") from None

    raise CliError(f"AppsFlyer API request failed for {endpoint}")


def decode_body(response: ApiResponse, endpoint: str) -> str:
    if not response.body:
        raise CliError(f"AppsFlyer API returned an empty response for {endpoint}")
    try:
        return response.body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CliError(f"AppsFlyer API returned non-UTF-8 data for {endpoint}") from exc


def validate_report_content_type(
    response: ApiResponse, expected_format: str, endpoint: str
) -> None:
    content_type = response.content_type.lower().split(";", 1)[0].strip()
    if expected_format == "json":
        valid = content_type == "application/json" or content_type.endswith("+json")
        expected = "JSON"
    else:
        valid = content_type in {"text/csv", "application/csv", "application/octet-stream"}
        expected = "CSV"
    if not valid:
        received = content_type or "missing Content-Type"
        raise CliError(
            f"AppsFlyer returned {received} for {endpoint}; expected a {expected} report"
        )


def merge_csv_documents(documents: Sequence[str]) -> str:
    merged_rows: list[list[str]] = []
    header: list[str] | None = None
    for document in documents:
        rows = list(csv.reader(io.StringIO(document)))
        if not rows:
            continue
        current_header = rows[0]
        if header is None:
            header = current_header
            merged_rows.append(header)
        elif current_header != header:
            raise CliError("AppsFlyer CSV headers changed between date chunks")
        merged_rows.extend(rows[1:])
    if header is None:
        raise CliError("AppsFlyer returned no CSV rows")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(merged_rows)
    return output.getvalue()


def parse_json_document(document: str, endpoint: str) -> Any:
    try:
        return json.loads(document)
    except json.JSONDecodeError as exc:
        raise CliError(
            f"AppsFlyer returned invalid JSON for {endpoint}: "
            f"line {exc.lineno}, column {exc.colno}"
        ) from None


def merge_json_documents(documents: Sequence[str], endpoint: str) -> str:
    parsed = [parse_json_document(document, endpoint) for document in documents]
    if len(parsed) == 1:
        merged: Any = parsed[0]
    elif all(isinstance(item, list) for item in parsed):
        merged = [row for item in parsed for row in item]
    elif all(isinstance(item, dict) and isinstance(item.get("data"), list) for item in parsed):
        merged = dict(parsed[0])
        merged["data"] = [row for item in parsed for row in item["data"]]
    else:
        raise CliError(
            "Cannot safely merge this multi-chunk JSON response; rerun with --format csv"
        )
    return json.dumps(merged, ensure_ascii=False, indent=2) + "\n"


def csv_to_json(document: str) -> str:
    rows = list(csv.DictReader(io.StringIO(document)))
    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


def fetch_chunked_report(
    endpoint: str,
    base_params: dict[str, Any],
    start: str,
    end: str,
    *,
    response_format: str,
    chunk_days: int | None = MAX_CHUNK_DAYS,
    requester: Callable[..., ApiResponse] = request_api,
) -> str:
    documents: list[str] = []
    ranges = date_chunks(start, end, chunk_days) if chunk_days else [(start, end)]
    for chunk_start, chunk_end in ranges:
        params = dict(base_params)
        params.update({"from": chunk_start, "to": chunk_end})
        accept = "application/json" if response_format == "json" else "text/csv"
        response = requester(endpoint, params, accept=accept)
        validate_report_content_type(response, response_format, endpoint)
        documents.append(decode_body(response, endpoint))
    if response_format == "json":
        return merge_json_documents(documents, endpoint)
    return merge_csv_documents(documents)


def parse_last_update(response: ApiResponse, endpoint: str) -> tuple[Any, str]:
    document = decode_body(response, endpoint).strip()
    try:
        return json.loads(document), "json"
    except json.JSONDecodeError:
        return document, "text"


def render_last_update(value: Any, value_format: str) -> str:
    if value_format == "json":
        return json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    return f"{value}\n"


def get_last_update(
    requester: Callable[..., ApiResponse] = request_api,
) -> tuple[Any, str]:
    endpoint = "/api/master-agg-data/lastupdate"
    response = requester(endpoint, {}, accept="application/json, text/plain")
    return parse_last_update(response, endpoint)


def list_param(values: list[str] | None) -> str | None:
    return ",".join(values) if values else None


def master_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {
        "groupings": list_param(args.groupings),
        "kpis": list_param(args.kpis),
    }
    optional = {
        "pid": list_param(args.pid),
        "c": list_param(args.campaign),
        "af_prt": list_param(args.agency),
        "af_channel": list_param(args.channel),
        "af_siteid": list_param(args.site_id),
        "geo": list_param(args.geo),
        "currency": args.currency,
        "timezone": args.timezone,
    }
    params.update({key: value for key, value in optional.items() if value is not None})
    for name, formula in args.calculated_kpi or []:
        if name in params:
            raise CliError(f"duplicate calculated KPI: {name}")
        params[name] = formula
    if args.format == "json":
        params["format"] = "json"
    return params


def pull_params(args: argparse.Namespace) -> dict[str, Any]:
    params = {
        "media_source": args.media_source,
        "category": args.category,
        "attribution_touch_type": args.attribution_touch_type,
        "currency": args.currency,
        "timezone": args.timezone,
    }
    cleaned = {key: value for key, value in params.items() if value is not None}
    if args.reattr:
        cleaned["reattr"] = "true"
    return cleaned


def default_output(command: str, output_format: str) -> Path:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = "json" if output_format == "json" else "csv" if output_format == "csv" else "txt"
    return Path("out") / f"appsflyer-{command}-{timestamp}-{os.getpid()}.{suffix}"


def write_output(
    document: str,
    output: str | None,
    command: str,
    output_format: str,
    *,
    stdout: bool = False,
) -> Path:
    destination = Path(output).expanduser() if output else default_output(command, output_format)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
    if stdout:
        sys.stdout.write(document)
    print(f"Saved AppsFlyer report to {destination}", file=sys.stderr)
    return destination


def add_date_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="date_from", type=iso_date, required=True)
    parser.add_argument("--to", dest="date_to", type=iso_date, required=True)


def add_output_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", help="Save the report to this path")
    parser.add_argument(
        "--stdout", action="store_true", help="Also print the complete report to stdout"
    )


def add_list_argument(parser: argparse.ArgumentParser, name: str, **kwargs: Any) -> None:
    parser.add_argument(name, type=comma_values, **kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query AppsFlyer Master and Aggregate Pull reporting APIs"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    last_update = subparsers.add_parser(
        "master-last-update", help="Get the latest Master API data update"
    )
    add_output_argument(last_update)

    master = subparsers.add_parser("master-report", help="Get a Master API report")
    master.add_argument("--app-id", required=True)
    add_date_arguments(master)
    add_list_argument(master, "--groupings", required=True)
    add_list_argument(master, "--kpis", required=True)
    master.add_argument("--calculated-kpi", type=calculated_kpi, action="append")
    add_list_argument(master, "--pid")
    add_list_argument(master, "--campaign")
    add_list_argument(master, "--agency")
    add_list_argument(master, "--channel")
    add_list_argument(master, "--site-id")
    add_list_argument(master, "--geo")
    master.add_argument("--currency", choices=["preferred", "USD"])
    master.add_argument("--timezone", choices=["preferred"])
    master.add_argument("--format", choices=["csv", "json"], default="csv")
    master.add_argument("--skip-last-update", action="store_true")
    add_output_argument(master)

    pull = subparsers.add_parser("pull", help="Get an Aggregate Pull API report")
    pull.add_argument("--report", choices=sorted(PULL_REPORT_PATHS), required=True)
    pull.add_argument("--app-id", required=True)
    add_date_arguments(pull)
    pull.add_argument("--media-source")
    pull.add_argument(
        "--category", choices=["standard", "facebook", "organic"]
    )
    pull.add_argument("--attribution-touch-type", choices=["impression"])
    pull.add_argument("--currency", choices=["preferred", "USD"])
    pull.add_argument("--reattr", action="store_true")
    pull.add_argument("--timezone")
    pull.add_argument("--format", choices=["csv", "json"], default="csv")
    add_output_argument(pull)

    return parser


def execute(args: argparse.Namespace) -> tuple[str, str, str]:
    if args.command == "master-last-update":
        value, value_format = get_last_update()
        return render_last_update(value, value_format), value_format, args.command

    validate_date_range(args.date_from, args.date_to)
    encoded_app_id = quote(args.app_id, safe="")

    if args.command == "master-report":
        validate_master_date_range(args.date_from, args.date_to)
        if not args.skip_last_update:
            value, value_format = get_last_update()
            freshness = render_last_update(value, value_format).strip()
            print(f"AppsFlyer Master last update: {freshness}", file=sys.stderr)
        endpoint = f"/api/master-agg-data/v4/app/{encoded_app_id}"
        document = fetch_chunked_report(
            endpoint,
            master_params(args),
            args.date_from,
            args.date_to,
            response_format=args.format,
            chunk_days=None,
        )
        return document, args.format, args.command

    if args.command == "pull":
        report_path = PULL_REPORT_PATHS[args.report]
        endpoint = f"/api/agg-data/export/app/{encoded_app_id}/{report_path}/v5"
        csv_document = fetch_chunked_report(
            endpoint,
            pull_params(args),
            args.date_from,
            args.date_to,
            response_format="csv",
            chunk_days=MAX_CHUNK_DAYS if args.report in DAILY_PULL_REPORTS else None,
        )
        if args.format == "json":
            return csv_to_json(csv_document), "json", f"pull-{args.report}"
        return csv_document, "csv", f"pull-{args.report}"

    raise CliError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document, output_format, command_name = execute(args)
        write_output(
            document,
            args.output,
            command_name,
            output_format,
            stdout=args.stdout,
        )
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
