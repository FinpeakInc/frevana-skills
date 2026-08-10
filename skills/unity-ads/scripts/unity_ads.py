#!/usr/bin/env python3
"""Safe CLI router for Unity Ads reporting and management APIs."""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import decimal
import http.client
import json
import os
import re
import secrets
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


SERVICES_BASE = "https://services.api.unity.com"
MONETIZATION_BASE = "https://monetization.api.unity.com"
MANAGEMENT_PREFIX = "/advertise/v1/organizations/{organizationId}/"

MONETIZATION_FIELDS = {
    "adrequest_count",
    "start_count",
    "view_count",
    "available_sum",
    "revenue_sum",
}
MONETIZATION_GROUPS = {"placement", "country", "platform", "game"}
MONETIZATION_SCALES = {"hour", "day", "week", "month", "year", "all"}
REPORT_SCALES = {"summary", "hour", "day", "week", "month"}
REPORT_NAMES = {"acquisitions", "skan"}
SAFE_PARAMETER = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:\[[A-Za-z0-9_-]+\])?$")
SAFE_TOKEN_LIST = re.compile(r"^[A-Za-z0-9_.-]+(?:,[A-Za-z0-9_.-]+)*$")
OBJECT_ID = re.compile(r"^[0-9a-fA-F]{24}$")
ORG_ID = re.compile(r"^[0-9]+$")


@dataclass(frozen=True)
class Action:
    method: str
    route: str
    description: str
    current_route: Optional[str] = None
    verify_route: Optional[str] = None
    verify_mode: str = "present"
    verify_keys: tuple[str, ...] = ()
    verify_ignore_fields: tuple[str, ...] = ()
    verify_ignore_null_fields: tuple[str, ...] = ()


ACTIONS: dict[str, Action] = {
    "list-apps": Action("GET", "apps", "List apps in the organization."),
    "get-app": Action("GET", "apps/{appId}", "Get one app."),
    "create-app": Action(
        "POST", "apps", "Create an app.", verify_route="apps/{responseId}"
    ),
    "update-app": Action(
        "PATCH",
        "apps/{appId}",
        "Partially update an app.",
        current_route="apps/{appId}",
        verify_route="apps/{appId}",
        verify_ignore_fields=("appLevelAttributionUpdateType",),
    ),
    "delete-app": Action(
        "DELETE",
        "apps/{appId}",
        "Permanently delete an app and its campaigns, bids, and creative packs.",
        current_route="apps/{appId}",
        verify_route="apps/{appId}",
        verify_mode="absent",
    ),
    "list-campaigns": Action(
        "GET", "apps/{appId}/campaigns", "List campaigns for an app."
    ),
    "get-campaign": Action(
        "GET", "apps/{appId}/campaigns/{campaignId}", "Get one campaign."
    ),
    "create-campaign": Action(
        "POST",
        "apps/{appId}/campaigns",
        "Create a campaign.",
        verify_route="apps/{appId}/campaigns/{responseId}",
        verify_ignore_null_fields=("attributionClickUrl", "attributionStartUrl"),
    ),
    "update-campaign": Action(
        "PATCH",
        "apps/{appId}/campaigns/{campaignId}",
        "Partially update a campaign, including its enabled state.",
        current_route="apps/{appId}/campaigns/{campaignId}",
        verify_route="apps/{appId}/campaigns/{campaignId}",
        verify_ignore_null_fields=("attributionClickUrl", "attributionStartUrl"),
    ),
    "get-budget": Action(
        "GET",
        "apps/{appId}/campaigns/{campaignId}/budget",
        "Get a campaign budget.",
    ),
    "update-budget": Action(
        "PATCH",
        "apps/{appId}/campaigns/{campaignId}/budget",
        "Partially update a campaign budget.",
        current_route="apps/{appId}/campaigns/{campaignId}/budget",
        verify_route="apps/{appId}/campaigns/{campaignId}/budget",
    ),
    "list-cpi-bids": Action(
        "GET", "apps/{appId}/campaigns/{campaignId}/cpi-bids", "List CPI bids."
    ),
    "update-cpi-bids": Action(
        "PATCH",
        "apps/{appId}/campaigns/{campaignId}/cpi-bids",
        "Partially update or remove CPI bids.",
        current_route="apps/{appId}/campaigns/{campaignId}/cpi-bids",
        verify_route="apps/{appId}/campaigns/{campaignId}/cpi-bids",
        verify_keys=("country",),
    ),
    "list-source-bids": Action(
        "GET",
        "apps/{appId}/campaigns/{campaignId}/source-bids",
        "List source bids.",
    ),
    "update-source-bids": Action(
        "PATCH",
        "apps/{appId}/campaigns/{campaignId}/source-bids",
        "Partially update or remove source bids.",
        current_route="apps/{appId}/campaigns/{campaignId}/source-bids",
        verify_route="apps/{appId}/campaigns/{campaignId}/source-bids",
        verify_keys=("country", "sourceAppId"),
    ),
    "list-roas-bids": Action(
        "GET", "apps/{appId}/campaigns/{campaignId}/roas-bids", "List ROAS bids."
    ),
    "list-retention-bids": Action(
        "GET",
        "apps/{appId}/campaigns/{campaignId}/retention-bids",
        "List retention bids.",
    ),
    "update-retention-bids": Action(
        "PATCH",
        "apps/{appId}/campaigns/{campaignId}/retention-bids",
        "Partially update retention bids.",
        current_route="apps/{appId}/campaigns/{campaignId}/retention-bids",
        verify_route="apps/{appId}/campaigns/{campaignId}/retention-bids",
        verify_keys=("country",),
    ),
    "list-event-optimization-bids": Action(
        "GET",
        "apps/{appId}/campaigns/{campaignId}/event-optimization-bids",
        "List event-optimization bids.",
    ),
    "list-creatives": Action(
        "GET", "apps/{appId}/creatives", "List uploaded creatives for an app."
    ),
    "list-creative-packs": Action(
        "GET", "apps/{appId}/creative-packs", "List creative packs for an app."
    ),
    "list-assigned-creative-packs": Action(
        "GET",
        "apps/{appId}/campaigns/{campaignId}/assigned-creative-packs",
        "List creative packs assigned to a campaign.",
    ),
    "get-targeting": Action(
        "GET",
        "apps/{appId}/campaigns/{campaignId}/targeting",
        "Get campaign targeting options.",
    ),
    "update-targeting": Action(
        "PATCH",
        "apps/{appId}/campaigns/{campaignId}/targeting",
        "Partially update campaign targeting options.",
        current_route="apps/{appId}/campaigns/{campaignId}/targeting",
        verify_route="apps/{appId}/campaigns/{campaignId}/targeting",
    ),
    "create-creative-pack": Action(
        "POST",
        "apps/{appId}/creative-packs",
        "Create a creative pack from existing creative IDs.",
        verify_route="apps/{appId}/creative-packs/{responseId}",
    ),
    "update-creative-pack": Action(
        "PATCH",
        "apps/{appId}/creative-packs/{resourceId}",
        "Partially update a creative pack.",
        current_route="apps/{appId}/creative-packs/{resourceId}",
        verify_route="apps/{appId}/creative-packs/{resourceId}",
    ),
    "delete-creative-pack": Action(
        "DELETE",
        "apps/{appId}/creative-packs/{resourceId}",
        "Delete a creative pack.",
        current_route="apps/{appId}/creative-packs/{resourceId}",
        verify_route="apps/{appId}/creative-packs/{resourceId}",
        verify_mode="absent",
    ),
}


class CliError(RuntimeError):
    pass


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


def url_origin(url: str) -> tuple[str, str, int]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise CliError("Unity API redirects must use HTTPS")
    if parsed.username or parsed.password:
        raise CliError("Unity API redirects must not contain URL credentials")
    return (parsed.scheme.lower(), parsed.hostname.lower(), parsed.port or 443)


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent credentials from crossing origins during API redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        if url_origin(req.full_url) != url_origin(redirected.full_url):
            redirected.remove_header("Authorization")
            redirected.remove_header("Proxy-Authorization")
        return redirected


API_OPENER = urllib.request.build_opener(SafeRedirectHandler())
STREAM_CHUNK_SIZE = 1024 * 1024


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def validate_owner_only_file(path_value: str, label: str) -> Path:
    path = Path(path_value).expanduser()
    try:
        info = path.lstat()
    except OSError as exc:
        raise CliError(f"Cannot read {label}: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise CliError(f"{label} must be a regular non-symlink file")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise CliError(f"{label} must be owned by the current user")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise CliError(f"{label} permissions must be 0400 or 0600")
    return path


def validate_secret_file(path_value: str) -> Path:
    return validate_owner_only_file(path_value, "Secret file")


def read_secret(env_name: str, file_value: Optional[str] = None) -> str:
    if file_value:
        value = validate_secret_file(file_value).read_text(encoding="utf-8").strip()
    else:
        value = os.environ.get(env_name, "").strip()
    if not value:
        raise CliError(f"Missing {env_name}")
    return value


def service_auth_headers(args: argparse.Namespace) -> dict[str, str]:
    bearer_file = getattr(args, "bearer_token_file", None)
    bearer = ""
    if bearer_file or os.environ.get("UNITY_ADS_SERVICE_ACCOUNT_BEARER_TOKEN"):
        bearer = read_secret("UNITY_ADS_SERVICE_ACCOUNT_BEARER_TOKEN", bearer_file)
    if bearer:
        return {"Authorization": f"Bearer {bearer}"}
    key_id = os.environ.get("UNITY_ADS_SERVICE_ACCOUNT_KEY_ID", "").strip()
    if getattr(args, "key_id_file", None):
        key_id = read_secret("UNITY_ADS_SERVICE_ACCOUNT_KEY_ID", args.key_id_file)
    secret = read_secret(
        "UNITY_ADS_SERVICE_ACCOUNT_SECRET",
        getattr(args, "service_secret_file", None),
    )
    if not key_id:
        raise CliError("Missing UNITY_ADS_SERVICE_ACCOUNT_KEY_ID")
    encoded = base64.b64encode(f"{key_id}:{secret}".encode()).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def organization_id(args: argparse.Namespace, monetization: bool = False) -> str:
    env_name = (
        "UNITY_ADS_MONETIZATION_ORG_ID" if monetization else "UNITY_ADS_ORGANIZATION_ID"
    )
    value = (getattr(args, "organization_id", None) or os.environ.get(env_name, "")).strip()
    if not value:
        raise CliError(f"Missing {env_name} or --organization-id")
    if not ORG_ID.fullmatch(value):
        raise CliError("Organization ID must contain digits only")
    return value


def parse_iso8601(value: str, label: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CliError(f"{label} must be an ISO 8601 date-time") from exc
    if parsed.tzinfo is None:
        raise CliError(f"{label} must include a timezone")
    return parsed


def validate_range(start: str, end: str) -> None:
    if parse_iso8601(start, "start") >= parse_iso8601(end, "end"):
        raise CliError("start must be earlier than end")


def comma_values(value: Optional[str], label: str) -> list[str]:
    if not value:
        return []
    if not SAFE_TOKEN_LIST.fullmatch(value):
        raise CliError(f"Invalid comma-separated {label}")
    return value.split(",")


def parse_extra_params(values: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise CliError("--param must use name=value")
        key, value = item.split("=", 1)
        if not SAFE_PARAMETER.fullmatch(key):
            raise CliError(f"Invalid query parameter name: {key}")
        if key in result:
            raise CliError(f"Duplicate query parameter: {key}")
        result[key] = value
    return result


def validate_api_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "services.api.unity.com",
        "monetization.api.unity.com",
    }:
        raise CliError("Refusing a non-Unity or non-HTTPS API URL")


def request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: Optional[bytes] = None,
    retries: int = 3,
    allow_statuses: Optional[set[int]] = None,
) -> Response:
    validate_api_url(url)
    allowed = allow_statuses or set()
    attempt = 0
    while True:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with API_OPENER.open(req, timeout=600) as response:
                return Response(
                    response.status,
                    dict(response.headers.items()),
                    response.read(),
                )
        except urllib.error.HTTPError as exc:
            error_body = exc.read()
            if exc.code in allowed:
                return Response(exc.code, dict(exc.headers.items()), error_body)
            retryable = method == "GET" and (exc.code == 429 or 500 <= exc.code <= 599)
            if retryable and attempt < retries:
                retry_after = exc.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else min(2**attempt, 8)
                time.sleep(delay)
                attempt += 1
                continue
            detail = sanitized_error_detail(error_body)
            raise CliError(f"Unity API returned HTTP {exc.code}{detail}") from None
        except urllib.error.URLError as exc:
            if method == "GET" and attempt < retries:
                time.sleep(min(2**attempt, 8))
                attempt += 1
                continue
            raise CliError(f"Unity API request failed: {exc.reason}") from None


def copy_response_stream(response: Any, stream: Any) -> None:
    while True:
        chunk = response.read(STREAM_CHUNK_SIZE)
        if not chunk:
            return
        stream.write(chunk)


def validate_output_target(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise CliError("Output path must not be a symlink")
    if path.exists() and not path.is_file():
        raise CliError("Output path must be a regular file")


def stream_report_request(
    url: str,
    headers: dict[str, str],
    output: Path,
    stdout: bool,
    require_eof_marker: bool = False,
    retries: int = 3,
) -> int:
    validate_api_url(url)
    validate_output_target(output)
    attempt = 0
    while True:
        temporary: Optional[Path] = None
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with API_OPENER.open(req, timeout=600) as response:
                status = response.status
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
                )
                temporary = Path(temporary_name)
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    copy_response_stream(response, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
            if require_eof_marker and status != 204:
                verify_eof_marker_file(temporary)
            os.replace(temporary, output)
            temporary = None
            eprint(f"Saved report: {output.resolve()}")
            if stdout:
                with output.open("rb") as stream:
                    copy_response_stream(stream, sys.stdout.buffer)
                if output.stat().st_size and not file_ends_with_newline(output):
                    print()
            return status
        except urllib.error.HTTPError as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if retryable and attempt < retries:
                retry_after = exc.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else min(2**attempt, 8)
                time.sleep(delay)
                attempt += 1
                continue
            detail = sanitized_error_detail(exc.read(2000))
            raise CliError(f"Unity API returned HTTP {exc.code}{detail}") from None
        except (urllib.error.URLError, http.client.IncompleteRead, TimeoutError) as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(min(2**attempt, 8))
                attempt += 1
                continue
            reason = getattr(exc, "reason", str(exc))
            raise CliError(f"Unity API request failed: {reason}") from None
        except Exception:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise


def sanitized_error_detail(body: bytes) -> str:
    if not body:
        return ""
    text = body.decode("utf-8", errors="replace")[:2000]
    for secret_name in (
        "UNITY_ADS_MONETIZATION_API_KEY",
        "UNITY_ADS_SERVICE_ACCOUNT_KEY_ID",
        "UNITY_ADS_SERVICE_ACCOUNT_SECRET",
        "UNITY_ADS_SERVICE_ACCOUNT_BEARER_TOKEN",
    ):
        secret = os.environ.get(secret_name, "")
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return f": {text}"


def secure_write(path: Path, body: bytes) -> None:
    validate_output_target(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(body)


def default_output(prefix: str, extension: str) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    nonce = secrets.token_hex(3)
    return Path("out") / f"unity-ads-{prefix}-{stamp}-{nonce}.{extension}"


def file_ends_with_newline(path: Path) -> bool:
    if path.stat().st_size == 0:
        return False
    with path.open("rb") as stream:
        stream.seek(-1, os.SEEK_END)
        return stream.read(1) == b"\n"


def verify_eof_marker_file(path: Path) -> None:
    marker_rows: Optional[int] = None
    data_rows = 0
    saw_header = False
    marker_seen = False
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
            for row in csv.reader(stream):
                if not row:
                    continue
                if marker_seen:
                    raise CliError("CSV response contains data after the EOF marker")
                joined = ",".join(row)
                if row[0].startswith("#__EOF__"):
                    match = re.search(r"(?:^|,)rows=(\d+)(?:,|$)", joined)
                    if not match:
                        raise CliError("CSV EOF marker is missing its row count")
                    marker_rows = int(match.group(1))
                    marker_seen = True
                    continue
                if not saw_header:
                    saw_header = True
                else:
                    data_rows += 1
    except OSError as exc:
        raise CliError(f"Cannot validate CSV report: {path}") from exc
    if marker_rows is None:
        raise CliError("CSV response is missing the requested EOF marker")
    if marker_rows != data_rows:
        raise CliError("CSV EOF marker row count does not match the downloaded report")


def run_monetization_report(args: argparse.Namespace) -> None:
    validate_range(args.start, args.end)
    fields = comma_values(args.fields, "fields")
    unknown_fields = set(fields) - MONETIZATION_FIELDS
    if unknown_fields:
        raise CliError(f"Unsupported monetization fields: {', '.join(sorted(unknown_fields))}")
    groups = comma_values(args.group_by, "group-by")
    unknown_groups = set(groups) - MONETIZATION_GROUPS
    if unknown_groups:
        raise CliError(f"Unsupported monetization groupBy values: {', '.join(sorted(unknown_groups))}")
    if args.scale not in MONETIZATION_SCALES:
        raise CliError("Unsupported monetization scale")
    org_id = organization_id(args, monetization=True)
    params = {
        "fields": args.fields,
        "scale": args.scale,
        "start": args.start,
        "end": args.end,
    }
    if args.group_by:
        params["groupBy"] = args.group_by
    if args.game_ids:
        comma_values(args.game_ids, "game IDs")
        params["gameIds"] = args.game_ids
    url = f"{MONETIZATION_BASE}/stats/v1/operate/organizations/{org_id}?{urllib.parse.urlencode(params)}"
    headers = {
        "Authorization": f"Token {read_secret('UNITY_ADS_MONETIZATION_API_KEY', args.api_key_file)}",
        "Accept": "application/json" if args.format == "json" else "text/csv",
        "User-Agent": "frevana-unity-ads-skill/1.0",
    }
    extension = "json" if args.format == "json" else "csv"
    output = Path(args.output) if args.output else default_output("monetization", extension)
    stream_report_request(url, headers, output, args.stdout)


def run_acquire_report(args: argparse.Namespace) -> None:
    validate_range(args.start, args.end)
    if args.report not in REPORT_NAMES:
        raise CliError("Unsupported Acquire report")
    if args.scale not in REPORT_SCALES:
        raise CliError("Unsupported Acquire report scale")
    comma_values(args.metrics, "metrics")
    comma_values(args.breakdowns, "breakdowns")
    org_id = organization_id(args)
    params = {
        "start": args.start,
        "end": args.end,
        "scale": args.scale,
        "metrics": args.metrics,
    }
    if args.breakdowns:
        params["breakdowns"] = args.breakdowns
    extra_params = parse_extra_params(args.param)
    reserved = set(params) & set(extra_params)
    if reserved:
        raise CliError(
            f"Do not override required report parameters with --param: {', '.join(sorted(reserved))}"
        )
    params.update(extra_params)
    if args.format == "json":
        params["format"] = "json"
    if args.eof_marker:
        if args.format == "json":
            raise CliError("--eof-marker is only valid for CSV reports")
        params["eofMarker"] = "true"
    url = (
        f"{SERVICES_BASE}/advertise/stats/v2/organizations/{org_id}/reports/"
        f"{args.report}?{urllib.parse.urlencode(params)}"
    )
    headers = service_auth_headers(args)
    headers.update({"Accept": "application/json" if args.format == "json" else "text/csv", "User-Agent": "frevana-unity-ads-skill/1.0"})
    extension = "json" if args.format == "json" else "csv"
    output = Path(args.output) if args.output else default_output(f"acquire-{args.report}", extension)
    status = stream_report_request(
        url,
        headers,
        output,
        args.stdout,
        require_eof_marker=args.eof_marker,
    )
    if status == 204:
        eprint("Unity returned 204: the report contains no data")


def validate_relative_management_path(value: str) -> str:
    if not value or value.startswith(("/", "http://", "https://")):
        raise CliError("Management path must be relative to the organization")
    if "?" in value or "#" in value or "\\" in value:
        raise CliError("Put query parameters in --param, not in --path")
    decoded = urllib.parse.unquote(value)
    if ".." in decoded.split("/") or "//" in value:
        raise CliError("Management path traversal is not allowed")
    if not re.fullmatch(r"[A-Za-z0-9._~/-]+", value):
        raise CliError("Management path contains unsupported characters")
    return value.strip("/")


def validate_object_id(value: Optional[str], label: str) -> str:
    if not value or not OBJECT_ID.fullmatch(value):
        raise CliError(f"{label} must be a 24-character hexadecimal ID")
    return value


def render_route(
    route: str, args: argparse.Namespace, response_id: Optional[str] = None
) -> str:
    values = {
        "appId": getattr(args, "app_id", None),
        "campaignId": getattr(args, "campaign_id", None),
        "resourceId": getattr(args, "resource_id", None),
        "responseId": response_id,
    }
    for placeholder in re.findall(r"{([^}]+)}", route):
        value = values.get(placeholder)
        if placeholder in {"appId", "campaignId", "responseId"}:
            value = validate_object_id(value, placeholder)
        elif not value or not re.fullmatch(r"[A-Za-z0-9._~-]+", value):
            raise CliError(f"Missing or invalid --{re.sub(r'(?<!^)(?=[A-Z])', '-', placeholder).lower()}")
        route = route.replace(f"{{{placeholder}}}", str(value))
    return validate_relative_management_path(route)


def management_url(org_id: str, relative_path: str, params: dict[str, str]) -> str:
    prefix = MANAGEMENT_PREFIX.format(organizationId=org_id)
    url = f"{SERVICES_BASE}{prefix}{validate_relative_management_path(relative_path)}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return url


def load_json_body(path_value: Optional[str]) -> tuple[Any, Optional[bytes]]:
    if not path_value:
        return None, None
    path = validate_owner_only_file(path_value, "JSON body file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"Cannot read valid JSON body file: {path}") from exc
    return value, json.dumps(value, separators=(",", ":")).encode("utf-8")


def json_or_text(body: bytes) -> Any:
    if not body:
        return None
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body.decode("utf-8", errors="replace")


def json_contains(expected: Any, actual: Any, path: str = "response") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise CliError(f"Mutation verification mismatch at {path}")
        for key, value in expected.items():
            if key not in actual:
                raise CliError(f"Mutation verification is missing {path}.{key}")
            json_contains(value, actual[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list):
            raise CliError(f"Mutation verification mismatch at {path}")
        unmatched = list(actual)
        for index, expected_item in enumerate(expected):
            for actual_index, actual_item in enumerate(unmatched):
                try:
                    json_contains(expected_item, actual_item, f"{path}[{index}]")
                except CliError:
                    continue
                unmatched.pop(actual_index)
                break
            else:
                raise CliError(f"Mutation verification is missing {path}[{index}]")
        return
    field = path.rsplit(".", 1)[-1]
    money_fields = {"bid", "baseBid", "maxBid", "daily", "total"}
    if field in money_fields and isinstance(expected, str) and isinstance(actual, str):
        try:
            if decimal.Decimal(expected) == decimal.Decimal(actual):
                return
        except decimal.InvalidOperation:
            pass
    if type(expected) is not type(actual) or expected != actual:
        raise CliError(f"Mutation verification mismatch at {path}")


def verify_keyed_updates(
    expected: Any, actual: Any, keys: tuple[str, ...]
) -> None:
    if not isinstance(expected, list) or not isinstance(actual, dict):
        raise CliError("Mutation verification received an unexpected bid response")
    actual_items = actual.get("results")
    if not isinstance(actual_items, list):
        raise CliError("Mutation verification response is missing results")
    for index, item in enumerate(expected):
        if not isinstance(item, dict) or any(key not in item for key in keys):
            raise CliError(f"Mutation payload is missing verification keys at request[{index}]")
        candidates = [
            candidate
            for candidate in actual_items
            if isinstance(candidate, dict)
            and all(candidate.get(key) == item[key] for key in keys)
        ]
        mutable_values = [value for key, value in item.items() if key not in keys]
        if any(value is None for value in mutable_values):
            if candidates:
                raise CliError(f"Deleted bid still exists after mutation at request[{index}]")
            continue
        for candidate in candidates:
            try:
                json_contains(item, candidate, f"response.results[{index}]")
            except CliError:
                continue
            break
        else:
            raise CliError(f"Updated bid was not verified at request[{index}]")


def verify_mutation_state(
    action: Optional[Action],
    method: str,
    expected: Any,
    actual: Any,
    verify_mode: str,
    verify_keys: tuple[str, ...] = (),
) -> None:
    if verify_mode == "absent":
        return
    if method == "DELETE":
        raise CliError("DELETE verification must require an absent resource")
    if action and isinstance(expected, dict):
        expected = {
            key: value
            for key, value in expected.items()
            if key not in action.verify_ignore_fields
            and not (key in action.verify_ignore_null_fields and value is None)
        }
    effective_keys = action.verify_keys if action and action.verify_keys else verify_keys
    if effective_keys:
        verify_keyed_updates(expected, actual, effective_keys)
        return
    if isinstance(expected, list) and isinstance(actual, dict):
        actual = actual.get("results")
    if isinstance(expected, list) and any(
        isinstance(item, dict) and any(value is None for value in item.values())
        for item in expected
    ):
        raise CliError("List deletion verification requires --verify-keys")
    json_contains(expected, actual)


def action_catalog() -> list[dict[str, str]]:
    return [
        {"name": name, "method": action.method, "description": action.description}
        for name, action in sorted(ACTIONS.items())
    ]


def run_management_list_actions(_: argparse.Namespace) -> None:
    print(json.dumps(action_catalog(), indent=2))


def run_management_describe(args: argparse.Namespace) -> None:
    action = ACTIONS.get(args.action)
    if not action:
        raise CliError(f"Unknown action: {args.action}")
    print(
        json.dumps(
            {
                "name": args.action,
                "method": action.method,
                "route": action.route,
                "description": action.description,
                "mutation": action.method != "GET",
                "current_route": action.current_route,
                "verify_route": action.verify_route,
                "verify_mode": action.verify_mode,
                "verify_keys": action.verify_keys,
            },
            indent=2,
        )
    )


def get_current_state(
    org_id: str, relative_path: str, headers: dict[str, str]
) -> tuple[int, Any]:
    response = request("GET", management_url(org_id, relative_path, {}), headers, allow_statuses={404})
    return response.status, json_or_text(response.body)


def run_management_call(args: argparse.Namespace) -> None:
    org_id = organization_id(args)
    action = ACTIONS.get(args.action) if args.action else None
    if args.action and not action:
        raise CliError(f"Unknown action: {args.action}")
    if action and (args.method or args.path):
        raise CliError("Use either --action or --method/--path, not both")
    if action:
        method = action.method
        relative_path = render_route(action.route, args)
        current_path = render_route(action.current_route, args) if action.current_route else None
        verify_path_template = action.verify_route
        verify_mode = action.verify_mode
    else:
        if not args.method or not args.path:
            raise CliError("Provide --action or both --method and --path")
        method = args.method.upper()
        if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            raise CliError("Unsupported management method")
        relative_path = validate_relative_management_path(args.path)
        current_path = validate_relative_management_path(args.current_path) if args.current_path else None
        verify_path_template = validate_relative_management_path(args.verify_path) if args.verify_path else None
        verify_mode = args.verify_mode
    params = parse_extra_params(args.param)
    body_value, body_bytes = load_json_body(args.body_file)
    if method == "GET" and body_bytes is not None:
        raise CliError("GET requests cannot include --body-file")
    if method in {"POST", "PATCH", "PUT"} and body_bytes is None:
        raise CliError(f"{method} requires --body-file")
    headers = service_auth_headers(args)
    headers.update({"Accept": "application/json", "User-Agent": "frevana-unity-ads-skill/1.0"})
    if body_bytes is not None:
        headers["Content-Type"] = "application/json"
    if method == "GET":
        response = request("GET", management_url(org_id, relative_path, params), headers)
        result = json_or_text(response.body)
        if args.output:
            output_body = json.dumps(result, indent=2).encode("utf-8") + b"\n"
            secure_write(Path(args.output), output_body)
            eprint(f"Saved result: {Path(args.output).resolve()}")
        else:
            print(json.dumps(result, indent=2) if not isinstance(result, str) else result)
        return
    if method in {"PATCH", "PUT", "DELETE"} and not current_path:
        raise CliError(f"{method} requires a current-state GET path")
    if not verify_path_template:
        raise CliError("Every mutation requires a verification GET path")
    if method == "DELETE" and verify_mode != "absent":
        raise CliError("DELETE requires --verify-mode absent")
    if method != "DELETE" and verify_mode == "absent":
        raise CliError("Only DELETE can use --verify-mode absent")
    verification_keys = tuple(
        comma_values(getattr(args, "verify_keys", None), "verification keys")
    )
    if action and verification_keys:
        raise CliError("Built-in actions define their own verification keys")
    current = None
    if current_path:
        current_status, current = get_current_state(org_id, current_path, headers)
        if current_status == 404:
            raise CliError("The mutation target does not exist")
    preview = {
        "execute": bool(args.execute),
        "method": method,
        "organizationId": org_id,
        "path": relative_path,
        "params": params,
        "body": body_value,
        "current": current,
        "verifyPath": verify_path_template,
        "verifyMode": verify_mode,
        "verifyKeys": verification_keys,
    }
    if args.action == "delete-app":
        preview["warning"] = (
            "Deleting an app is unrecoverable and also deletes its campaigns, bids, "
            "and creative packs."
        )
    if not args.execute:
        print(json.dumps(preview, indent=2))
        eprint("Preview only. Re-run the same command with --execute after explicit confirmation.")
        return
    response = request(
        method,
        management_url(org_id, relative_path, params),
        headers,
        body=body_bytes,
        retries=0,
    )
    result = json_or_text(response.body)
    response_id = result.get("id") if isinstance(result, dict) else None
    if action and verify_path_template:
        verify_path = render_route(verify_path_template, args, response_id=response_id)
    else:
        verify_path = validate_relative_management_path(verify_path_template)
    verify_status, verified = get_current_state(org_id, verify_path, headers)
    if verify_mode == "absent":
        if verify_status != 404:
            raise CliError("Mutation returned success but verification target still exists")
    elif verify_status == 404:
        raise CliError("Mutation returned success but verification target was not found")
    else:
        verify_mutation_state(
            action,
            method,
            body_value,
            verified,
            verify_mode,
            verification_keys,
        )
    print(
        json.dumps(
            {
                "status": response.status,
                "result": result,
                "verification": {
                    "mode": verify_mode,
                    "status": verify_status,
                    "value": verified,
                },
            },
            indent=2,
        )
    )


def run_check(_: argparse.Namespace) -> None:
    result = {
        "python": sys.version.split()[0],
        "python_supported": sys.version_info >= (3, 9),
        "monetization": {
            "organization_id": bool(os.environ.get("UNITY_ADS_MONETIZATION_ORG_ID")),
            "api_key": bool(os.environ.get("UNITY_ADS_MONETIZATION_API_KEY")),
        },
        "acquire": {
            "organization_id": bool(os.environ.get("UNITY_ADS_ORGANIZATION_ID")),
            "basic_credentials": bool(
                os.environ.get("UNITY_ADS_SERVICE_ACCOUNT_KEY_ID")
                and os.environ.get("UNITY_ADS_SERVICE_ACCOUNT_SECRET")
            ),
            "bearer_token": bool(
                os.environ.get("UNITY_ADS_SERVICE_ACCOUNT_BEARER_TOKEN")
            ),
        },
        "hosts": [MONETIZATION_BASE, SERVICES_BASE],
    }
    print(json.dumps(result, indent=2))
    if not result["python_supported"]:
        raise CliError("Python 3.9 or newer is required")


def add_service_auth_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--key-id-file")
    parser.add_argument("--service-secret-file")
    parser.add_argument("--bearer-token-file")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="unity_ads", description=__doc__)
    subparsers = parser.add_subparsers(dest="module", required=True)
    check = subparsers.add_parser("check", help="Check runtime and credential presence")
    check.set_defaults(handler=run_check)

    monetization = subparsers.add_parser("monetization")
    monetization_sub = monetization.add_subparsers(dest="command", required=True)
    mon_report = monetization_sub.add_parser("report")
    mon_report.add_argument("--organization-id")
    mon_report.add_argument("--api-key-file")
    mon_report.add_argument("--start", required=True)
    mon_report.add_argument("--end", required=True)
    mon_report.add_argument("--fields", required=True)
    mon_report.add_argument("--group-by")
    mon_report.add_argument("--game-ids")
    mon_report.add_argument("--scale", required=True)
    mon_report.add_argument("--format", choices=("csv", "json"), default="csv")
    mon_report.add_argument("--output")
    mon_report.add_argument("--stdout", action="store_true")
    mon_report.set_defaults(handler=run_monetization_report)

    reporting = subparsers.add_parser("reporting")
    reporting_sub = reporting.add_subparsers(dest="command", required=True)
    acquire_report = reporting_sub.add_parser("report")
    acquire_report.add_argument("--organization-id")
    add_service_auth_arguments(acquire_report)
    acquire_report.add_argument("--report", choices=sorted(REPORT_NAMES), required=True)
    acquire_report.add_argument("--start", required=True)
    acquire_report.add_argument("--end", required=True)
    acquire_report.add_argument("--scale", choices=sorted(REPORT_SCALES), required=True)
    acquire_report.add_argument("--metrics", required=True)
    acquire_report.add_argument("--breakdowns")
    acquire_report.add_argument("--param", action="append", default=[])
    acquire_report.add_argument("--format", choices=("csv", "json"), default="csv")
    acquire_report.add_argument("--eof-marker", action="store_true")
    acquire_report.add_argument("--output")
    acquire_report.add_argument("--stdout", action="store_true")
    acquire_report.set_defaults(handler=run_acquire_report)

    management = subparsers.add_parser("management")
    management_sub = management.add_subparsers(dest="command", required=True)
    list_actions = management_sub.add_parser("list-actions")
    list_actions.set_defaults(handler=run_management_list_actions)
    describe = management_sub.add_parser("describe")
    describe.add_argument("--action", required=True)
    describe.set_defaults(handler=run_management_describe)
    call = management_sub.add_parser("call")
    call.add_argument("--organization-id")
    add_service_auth_arguments(call)
    call.add_argument("--action")
    call.add_argument("--method")
    call.add_argument("--path")
    call.add_argument("--app-id")
    call.add_argument("--campaign-id")
    call.add_argument("--resource-id")
    call.add_argument("--param", action="append", default=[])
    call.add_argument("--body-file")
    call.add_argument("--current-path")
    call.add_argument("--verify-path")
    call.add_argument("--verify-mode", choices=("present", "absent"), default="present")
    call.add_argument("--verify-keys")
    call.add_argument("--execute", action="store_true")
    call.add_argument("--output")
    call.set_defaults(handler=run_management_call)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.handler(args)
        return 0
    except CliError as exc:
        eprint(f"error: {exc}")
        return 2
    except KeyboardInterrupt:
        eprint("error: interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
