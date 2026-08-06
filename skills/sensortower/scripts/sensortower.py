#!/usr/bin/env python3
"""Dependency-free Sensor Tower API CLI for the sensortower agent skill."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

DEFAULT_API_BASE_URL = "https://api.sensortower.com"
DEFAULT_TIMEOUT = 30
COUNTRY_RE = re.compile(r"^(?:[A-Z]{2}|WW)$")


class CliError(Exception):
    """Expected user-facing failure that is safe to print."""


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def iso_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must use YYYY-MM-DD") from exc
    return value


def countries(value: str) -> list[str]:
    parsed = [part.strip().upper() for part in value.split(",") if part.strip()]
    if not parsed:
        raise argparse.ArgumentTypeError("must include at least one country code")
    invalid = [country for country in parsed if not COUNTRY_RE.fullmatch(country)]
    if invalid:
        raise argparse.ArgumentTypeError(
            "invalid country code(s): " + ", ".join(invalid)
        )
    return parsed


def validate_date_range(start: str | None, end: str | None) -> None:
    if start and end and dt.date.fromisoformat(start) > dt.date.fromisoformat(end):
        raise CliError("start date must not be after end date")


def api_base_url() -> str:
    base = os.environ.get("SENSORTOWER_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.params or parsed.query or parsed.fragment:
        raise CliError("SENSORTOWER_API_BASE_URL must be an HTTPS origin")
    return base


def auth_token() -> str:
    token = os.environ.get("SENSORTOWER_AUTH_TOKEN", "").strip()
    if not token:
        raise CliError("SENSORTOWER_AUTH_TOKEN is not set")
    return token


def redact(text: str, secrets: Iterable[str]) -> str:
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


def request_json(
    endpoint: str,
    params: dict[str, Any],
    *,
    opener=urlopen,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    token = auth_token()
    query_params = {**params, "auth_token": token}
    url = f"{api_base_url()}{endpoint}?{urlencode(query_params, doseq=True)}"
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "frevana-sensortower-skill/1"},
    )
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw_error = exc.read(2048).decode("utf-8", errors="replace")
        detail = redact(raw_error.strip(), [token])
        message = f"Sensor Tower API returned HTTP {exc.code} for {endpoint}"
        if detail:
            message += f": {detail}"
        raise CliError(message) from None
    except URLError as exc:
        reason = redact(str(exc.reason), [token])
        raise CliError(f"Sensor Tower API request failed for {endpoint}: {reason}") from None
    except TimeoutError:
        raise CliError(f"Sensor Tower API request timed out for {endpoint}") from None

    if not raw.strip():
        raise CliError(f"Sensor Tower API returned an empty response for {endpoint}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(
            f"Sensor Tower API returned invalid JSON for {endpoint}: line {exc.lineno}, column {exc.colno}"
        ) from None


def add_output_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", help="Write the same validated JSON to this file")


def add_date_range(parser: argparse.ArgumentParser, *, required: bool) -> None:
    parser.add_argument("--start", type=iso_date, required=required)
    parser.add_argument("--end", type=iso_date, required=required)


def build_parser(today: dt.date | None = None) -> argparse.ArgumentParser:
    today = today or dt.date.today()
    parser = argparse.ArgumentParser(description="Query Sensor Tower app intelligence")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search apps or publishers")
    search.add_argument("--term", required=True)
    search.add_argument("--entity-type", choices=["app", "publisher"], default="app")
    search.add_argument("--os", choices=["unified", "ios", "android"], default="unified")
    search.add_argument("--limit", type=positive_int, default=10)
    add_output_argument(search)

    sales = subparsers.add_parser("sales", help="Query downloads and revenue estimates")
    identity = sales.add_mutually_exclusive_group(required=True)
    identity.add_argument("--app-id")
    identity.add_argument("--publisher-id")
    sales.add_argument("--os", choices=["ios", "android"], required=True)
    sales.add_argument("--countries", type=countries, required=True)
    add_date_range(sales, required=True)
    sales.add_argument(
        "--granularity",
        choices=["daily", "weekly", "monthly", "quarterly"],
        default="monthly",
    )
    add_output_argument(sales)

    charts = subparsers.add_parser("top-charts", help="Query Sensor Tower top charts")
    charts.add_argument("--measure", choices=["revenue", "units", "DAU", "WAU", "MAU"], default="revenue")
    charts.add_argument("--countries", type=countries, default=["US"])
    charts.add_argument("--category")
    charts.add_argument("--limit", type=positive_int, default=100)
    charts.add_argument("--start", type=iso_date, default=(today - dt.timedelta(days=30)).isoformat())
    charts.add_argument("--end", type=iso_date, default=today.isoformat())
    charts.add_argument("--os", choices=["unified", "ios", "android"], default="unified")
    add_output_argument(charts)

    active = subparsers.add_parser("active-users", help="Query DAU, WAU, or MAU")
    active.add_argument("--app-id", required=True)
    active.add_argument("--os", choices=["ios", "android"], required=True)
    active.add_argument("--metric", choices=["DAU", "WAU", "MAU"], default="DAU")
    active.add_argument("--countries", type=countries, required=True)
    add_date_range(active, required=True)
    add_output_argument(active)

    publisher = subparsers.add_parser("publisher-apps", help="Query a publisher's apps")
    publisher.add_argument("--publisher-id", required=True)
    publisher.add_argument("--os", choices=["unified", "ios", "android"], default="unified")
    add_output_argument(publisher)

    ads = subparsers.add_parser("ad-intelligence", help="Query advertising intelligence")
    ads.add_argument("--action", choices=["overview", "top-advertisers", "creatives"], required=True)
    ads.add_argument("--app-id")
    ads.add_argument("--countries", type=countries, default=["US"])
    ads.add_argument("--category")
    ads.add_argument("--limit", type=positive_int, default=20)
    ads.add_argument("--start", type=iso_date, default=(today - dt.timedelta(days=30)).isoformat())
    ads.add_argument("--end", type=iso_date, default=today.isoformat())
    ads.add_argument("--networks")
    add_output_argument(ads)

    return parser


def endpoint_and_params(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    if args.command == "search":
        return f"/v1/{args.os}/search_entities", {
            "term": args.term,
            "entity_type": args.entity_type,
            "limit": args.limit,
        }

    if args.command == "sales":
        validate_date_range(args.start, args.end)
        params: dict[str, Any] = {
            "countries[]": args.countries,
            "date_granularity": args.granularity,
            "start_date": args.start,
            "end_date": args.end,
        }
        params["app_ids[]" if args.app_id else "publisher_ids[]"] = (
            args.app_id or args.publisher_id
        )
        return f"/v1/{args.os}/sales_report_estimates", params

    if args.command == "top-charts":
        validate_date_range(args.start, args.end)
        params = {
            "measure": args.measure,
            "countries": ",".join(args.countries),
            "limit": args.limit,
            "start_date": args.start,
            "end_date": args.end,
        }
        if args.category:
            params["category"] = args.category
        endpoint_os = "itunes" if args.os == "ios" else args.os
        return f"/v1/{endpoint_os}/top_charts", params

    if args.command == "active-users":
        validate_date_range(args.start, args.end)
        endpoint_os = "itunes" if args.os == "ios" else args.os
        return f"/v1/{endpoint_os}/active_users", {
            "app_id": args.app_id,
            "metric": args.metric.lower(),
            "countries": ",".join(args.countries),
            "start_date": args.start,
            "end_date": args.end,
        }

    if args.command == "publisher-apps":
        endpoint_os = "itunes" if args.os == "ios" else args.os
        return f"/v1/{endpoint_os}/publisher_apps", {"publisher_id": args.publisher_id}

    if args.command == "ad-intelligence":
        validate_date_range(args.start, args.end)
        if args.action in {"overview", "creatives"} and not args.app_id:
            raise CliError(f"--app-id is required for ad-intelligence {args.action}")
        action_path = args.action.replace("-", "_")
        params = {
            "start_date": args.start,
            "end_date": args.end,
            "countries": ",".join(args.countries),
            "limit": args.limit,
        }
        for key in ("app_id", "category", "networks"):
            value = getattr(args, key)
            if value:
                params[key] = value
        return f"/v1/unified/ad_intel/{action_path}", params

    raise CliError(f"unsupported command: {args.command}")


def write_output(data: Any, output: str | None) -> None:
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if output:
        destination = Path(output).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
        print(f"Saved Sensor Tower JSON to {destination}", file=sys.stderr)
    sys.stdout.write(rendered)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        endpoint, params = endpoint_and_params(args)
        data = request_json(endpoint, params)
        write_output(data, args.output)
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

