#!/usr/bin/env python3
"""Safe Moloco Ads API CLI for analytics, exports, and entity management."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


API_ORIGIN = "https://api.moloco.cloud"
API_PREFIX = "/cm/v1"
DEFAULT_API_VERSION = "v1.10"
DEFAULT_TIMEOUT = 60
DEFAULT_POLL_TIMEOUT = 600
MAX_ATTEMPTS = 4
TOKEN_LIFETIME_SECONDS = 16 * 60 * 60
TOKEN_CACHE_MARGIN_SECONDS = 15 * 60
MAX_ANALYTICS_DAYS = 184
MAX_REPORT_DAYS = 31
MAX_ANALYTICS_ROWS = 10_000
USER_AGENT = "frevana-moloco-ads-skill/1"

RESOURCE_PATHS = {
    "ad-accounts": "/cm/v1/ad-accounts",
    "products": "/cm/v1/products",
    "campaigns": "/cm/v1/campaigns",
    "ad-groups": "/cm/v1/ad-groups",
    "creative-groups": "/cm/v1/creative-groups",
    "creatives": "/cm/v1/creatives",
    "audience-targets": "/cm/v1/audience-targets",
    "customer-sets": "/cm/v1/customer-sets",
    "tracking-links": "/cm/v1/tracking-links",
}

RESOURCE_ALIASES = {
    "ad-account": "ad-accounts",
    "product": "products",
    "campaign": "campaigns",
    "ad-group": "ad-groups",
    "creative-group": "creative-groups",
    "creative": "creatives",
    "audience-target": "audience-targets",
    "customer-set": "customer-sets",
    "tracking-link": "tracking-links",
}

CREATE_REQUIRED_QUERY = {
    "ad-accounts": (),
    "products": ("ad_account_id",),
    "campaigns": ("ad_account_id", "product_id"),
    "ad-groups": ("ad_account_id", "product_id", "campaign_id"),
    "creative-groups": ("ad_account_id", "product_id"),
    "creatives": ("ad_account_id", "product_id"),
    "audience-targets": ("ad_account_id",),
    "customer-sets": ("ad_account_id",),
    "tracking-links": ("ad_account_id", "product_id"),
}

REPORT_DIMENSIONS = {
    "DATE", "APP_OR_SITE", "CAMPAIGN", "AD_GROUP", "CREATIVE_GROUP",
    "CREATIVE", "EXCHANGE", "SUB_PUBLISHER", "TRAFFIC", "SKAN",
}
REPORT_OPTIONAL_METRICS = {
    "VIDEO_PLAY_PROGRESS", "ENGAGED_VIEWS", "ENGAGED_CLICKS",
}
LOG_TYPES = {"IMP", "CLICK", "CONVERSION", "SKAN_CONVERSION", "ENGAGED_VIEW"}
LOG_FORMATS = {"CSV", "AVRO"}
SECRET_KEY_PATTERN = re.compile(r"(token|secret|password|api[_-]?key|authorization)", re.I)
VERSION_PATTERN = re.compile(r"^v1\.\d+(?:\.\d+)?$")


class CliError(Exception):
    """Expected failure safe to show to the user."""


class ApiHttpError(CliError):
    def __init__(self, code: int, endpoint: str, detail: str, headers: Mapping[str, str] | None = None):
        self.code = code
        self.endpoint = endpoint
        self.detail = detail
        self.headers = headers or {}
        message = f"Moloco Ads API returned HTTP {code} for {endpoint}"
        if detail:
            message += f": {detail}"
        if code == 401:
            message += ". Verify MOLOCO_ADS_API_KEY and Moloco Ads account access"
        elif code == 403:
            message += ". Verify the workplace and ad-account role for this API key"
        elif code == 429:
            message += ". The Moloco API quota is exhausted; wait for the reset window"
        super().__init__(message)


class ApiResponse:
    def __init__(self, body: bytes, status: int = 200, content_type: str = "", headers: Mapping[str, str] | None = None):
        self.body = body
        self.status = status
        self.content_type = content_type
        self.headers = dict(headers or {})


def iso_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must use YYYY-MM-DD") from exc
    return value


def comma_values(value: str) -> list[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("must include at least one comma-separated value")
    return values


def positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return result


def validate_date_range(start: str, end: str, maximum_days: int | None = None) -> int:
    start_date = dt.date.fromisoformat(start)
    end_date = dt.date.fromisoformat(end)
    if start_date > end_date:
        raise CliError("--from must not be after --to")
    span = (end_date - start_date).days + 1
    if maximum_days is not None and span > maximum_days:
        raise CliError(f"date range supports at most {maximum_days} inclusive days")
    return span


def api_version() -> str:
    version = os.environ.get("MOLOCO_ADS_API_VERSION", DEFAULT_API_VERSION).strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise CliError("MOLOCO_ADS_API_VERSION must look like v1.10")
    return version


def api_key() -> str:
    value = os.environ.get("MOLOCO_ADS_API_KEY", "").strip()
    if not value:
        raise CliError("MOLOCO_ADS_API_KEY is not set")
    return value


def token_cache_path() -> Path:
    override = os.environ.get("MOLOCO_ADS_TOKEN_CACHE", "").strip()
    if override:
        return Path(override).expanduser()
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_root / "moloco-ads" / "token.json"


def api_key_fingerprint(value: str | None = None) -> str:
    key = api_key() if value is None else value
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def redact(text: str, secrets: Iterable[str]) -> str:
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


def redact_url(value: str) -> str:
    try:
        parsed = urlparse(value)
    except ValueError:
        return value
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return value

    netloc = parsed.netloc
    if "@" in netloc:
        netloc = f"[REDACTED]@{netloc.rsplit('@', 1)[1]}"

    query = "[REDACTED]" if parsed.query else ""
    fragment = "[REDACTED]" if parsed.fragment else ""
    return parsed._replace(netloc=netloc, query=query, fragment=fragment).geturl()


def redact_object(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SECRET_KEY_PATTERN.search(str(key)) else redact_object(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_object(item) for item in value]
    if isinstance(value, str):
        return redact_url(value)
    return value


def response_content_type(response: Any) -> str:
    headers = getattr(response, "headers", None)
    if headers is None:
        return ""
    getter = getattr(headers, "get_content_type", None)
    if callable(getter):
        return str(getter()).lower()
    value = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
    return str(value).split(";", 1)[0].strip().lower()


def response_headers(response: Any) -> dict[str, str]:
    headers = getattr(response, "headers", None)
    if headers is None:
        return {}
    try:
        return {str(key): str(value) for key, value in headers.items()}
    except AttributeError:
        return dict(headers)


def retry_delay(headers: Mapping[str, str], attempt: int, now: Callable[[], float] = time.time) -> float:
    retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), 30.0)
        except ValueError:
            pass
    reset = headers.get("X-Rate-Limit-Reset") or headers.get("x-rate-limit-reset")
    if reset:
        try:
            return min(max(float(reset) - now(), 0.0), 30.0)
        except ValueError:
            pass
    return min(float(2**attempt), 30.0)


def perform_request(
    request: Request,
    endpoint_label: str,
    secrets: Iterable[str],
    *,
    retry_safe: bool,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
    timeout: int = DEFAULT_TIMEOUT,
    max_attempts: int = MAX_ATTEMPTS,
) -> ApiResponse:
    attempts = max_attempts if retry_safe else 1
    for attempt in range(attempts):
        try:
            with opener(request, timeout=timeout) as response:
                return ApiResponse(
                    response.read(),
                    int(getattr(response, "status", 200)),
                    response_content_type(response),
                    response_headers(response),
                )
        except HTTPError as exc:
            headers = response_headers(exc)
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if retry_safe and retryable and attempt + 1 < attempts:
                sleeper(retry_delay(headers, attempt))
                continue
            detail = exc.read(8192).decode("utf-8", errors="replace").strip()
            raise ApiHttpError(exc.code, endpoint_label, redact(detail, secrets), headers) from None
        except URLError as exc:
            reason = redact(str(exc.reason), secrets)
            raise CliError(f"Moloco request failed for {endpoint_label}: {reason}") from None
        except TimeoutError:
            raise CliError(f"Moloco request timed out for {endpoint_label}") from None
    raise CliError(f"Moloco request failed for {endpoint_label}")


def parse_json_response(response: ApiResponse, endpoint: str) -> dict[str, Any]:
    content_type = response.content_type
    if content_type and content_type != "application/json" and not content_type.endswith("+json"):
        raise CliError(f"Moloco returned {content_type} for {endpoint}; expected JSON")
    try:
        value = json.loads(response.body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliError(f"Moloco returned invalid JSON for {endpoint}") from exc
    if not isinstance(value, dict):
        raise CliError(f"Moloco returned a non-object JSON response for {endpoint}")
    return value


def read_cached_token(now: Callable[[], float] = time.time) -> str | None:
    path = token_cache_path()
    try:
        if path.is_symlink() or not path.is_file():
            return None
        metadata = path.stat()
        if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            return None
        document = json.loads(path.read_text(encoding="utf-8"))
        token = document.get("token")
        expires_at = float(document.get("expires_at", 0))
        fingerprint = document.get("api_key_fingerprint")
        if (
            isinstance(token, str)
            and token
            and fingerprint == api_key_fingerprint()
            and expires_at > now() + TOKEN_CACHE_MARGIN_SECONDS
        ):
            return token
    except (CliError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return None


def write_cached_token(token: str, expires_at: float, fingerprint: str) -> None:
    path = token_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise CliError(f"refusing to use symlink token-cache directory: {path.parent}")
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    document = json.dumps(
        {
            "token": token,
            "expires_at": expires_at,
            "api_key_fingerprint": fingerprint,
        },
        separators=(",", ":"),
    )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            handle.write(document)
            temporary = Path(handle.name)
        temporary.chmod(0o600)
        temporary.replace(path)
        path.chmod(0o600)
    except OSError as exc:
        raise CliError(f"could not write Moloco token cache: {exc}") from None
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def issue_access_token(
    *,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> str:
    key = api_key()
    payload = json.dumps({"api_key": key}, separators=(",", ":")).encode("utf-8")
    request = Request(
        f"{API_ORIGIN}{API_PREFIX}/auth/tokens",
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Moloco-Cloud-Api-Version": api_version(),
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    response = perform_request(
        request,
        f"{API_PREFIX}/auth/tokens",
        [key],
        retry_safe=True,
        opener=opener,
        sleeper=sleeper,
    )
    document = parse_json_response(response, f"{API_PREFIX}/auth/tokens")
    token = document.get("token")
    token_type = document.get("token_type")
    if not isinstance(token, str) or not token:
        raise CliError("Moloco token response did not contain a token")
    if token_type not in (None, "AUTH_TOKEN"):
        raise CliError(f"Moloco returned unsupported token type {token_type!r}")
    write_cached_token(token, now() + TOKEN_LIFETIME_SECONDS, api_key_fingerprint(key))
    return token


def access_token(force_refresh: bool = False, **kwargs: Any) -> str:
    if not force_refresh:
        cached = read_cached_token()
        if cached:
            return cached
    return issue_access_token(**kwargs)


def validate_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if (
        not endpoint.startswith(f"{API_PREFIX}/")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or ".." in parsed.path.split("/")
    ):
        raise CliError("API endpoint must be a fixed path under /cm/v1 without a query")


def validate_query(params: Mapping[str, Any]) -> None:
    for key, value in params.items():
        if not isinstance(key, str) or not key or isinstance(value, dict):
            raise CliError("query parameters must be a flat JSON object")
        values = value if isinstance(value, list) else [value]
        if any(isinstance(item, (dict, list)) for item in values):
            raise CliError("query parameter arrays may contain only scalar values")


def api_request(
    method: str,
    endpoint: str,
    *,
    params: Mapping[str, Any] | None = None,
    body: Mapping[str, Any] | None = None,
    retry_safe: bool | None = None,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
    token_resolver: Callable[..., str] = access_token,
) -> ApiResponse:
    method = method.upper()
    validate_endpoint(endpoint)
    query_params = dict(params or {})
    validate_query(query_params)
    query = urlencode(query_params, doseq=True)
    url = f"{API_ORIGIN}{endpoint}"
    if query:
        url = f"{url}?{query}"
    payload = None
    if body is not None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    safe = method == "GET" if retry_safe is None else retry_safe

    token = token_resolver()
    for auth_attempt in range(2):
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Moloco-Cloud-Api-Version": api_version(),
            "User-Agent": USER_AGENT,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=payload, headers=headers, method=method)
        try:
            return perform_request(
                request,
                endpoint,
                [token, api_key()],
                retry_safe=safe,
                opener=opener,
                sleeper=sleeper,
            )
        except ApiHttpError as exc:
            if exc.code == 401 and auth_attempt == 0 and safe:
                token = token_resolver(force_refresh=True)
                continue
            if exc.code == 401 and auth_attempt == 0:
                token_resolver(force_refresh=True)
                refresh_detail = (
                    f"The access token was refreshed, but the {method} request was not retried. "
                    "Rerun it deliberately"
                )
                detail = f"{exc.detail}. {refresh_detail}" if exc.detail else refresh_detail
                raise ApiHttpError(exc.code, endpoint, detail, exc.headers) from None
            raise
    raise CliError(f"Moloco authentication failed for {endpoint}")


def api_json(method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
    return parse_json_response(api_request(method, endpoint, **kwargs), endpoint)


def load_json_object(path: str | None, inline: str | None, label: str) -> dict[str, Any]:
    if path and inline:
        raise CliError(f"use only one of --{label}-file or --{label}-json")
    try:
        if path:
            candidate = Path(path).expanduser()
            if candidate.is_symlink() or not candidate.is_file():
                raise CliError(f"--{label}-file must be a regular, non-symlink file")
            value = json.loads(candidate.read_text(encoding="utf-8"))
        elif inline:
            value = json.loads(inline)
        else:
            return {}
    except json.JSONDecodeError as exc:
        raise CliError(f"--{label} must contain valid JSON: {exc.msg}") from None
    except OSError as exc:
        raise CliError(f"could not read --{label}-file: {exc}") from None
    if not isinstance(value, dict):
        raise CliError(f"--{label} must contain a JSON object")
    return value


def common_query(args: argparse.Namespace) -> dict[str, Any]:
    query = load_json_object(getattr(args, "params_file", None), getattr(args, "params_json", None), "params")
    for argument, field in (
        ("ad_account_id", "ad_account_id"),
        ("product_id", "product_id"),
        ("campaign_id", "campaign_id"),
        ("inquiry_option", "inquiry_option"),
    ):
        value = getattr(args, argument, None)
        if value is not None:
            query[field] = value
    states = getattr(args, "states", None)
    if states:
        query["states"] = states
    validate_query(query)
    return query


def require_query(query: Mapping[str, Any], fields: Iterable[str], action: str) -> None:
    missing = [field for field in fields if not query.get(field)]
    if missing:
        flags = ", ".join("--" + field.replace("_", "-") for field in missing)
        raise CliError(f"{action} requires {flags}")


def normalize_resource(value: str) -> str:
    resource = RESOURCE_ALIASES.get(value, value)
    if resource not in RESOURCE_PATHS:
        raise CliError(f"unsupported resource {value!r}")
    return resource


def item_endpoint(resource: str, identifier: str) -> str:
    if not identifier.strip():
        raise CliError("resource ID must not be empty")
    return f"{RESOURCE_PATHS[resource]}/{quote(identifier, safe='')}"


def output_path(action: str, extension: str, selected: str | None = None) -> Path:
    if selected:
        return Path(selected).expanduser()
    safe_action = re.sub(r"[^A-Za-z0-9_-]+", "-", action).strip("-") or "result"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path.cwd() / "out" / f"moloco-ads-{safe_action}-{stamp}.{extension}"


def write_bytes(path: Path, body: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise CliError(f"refusing to overwrite symlink output: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
        path.chmod(0o600)
    except OSError as exc:
        raise CliError(f"could not write output file {path}: {exc}") from None
    return path.resolve()


def emit_json(document: Mapping[str, Any], action: str, args: argparse.Namespace) -> None:
    body = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if getattr(args, "stdout", False):
        sys.stdout.write(body.decode("utf-8"))
        return
    path = write_bytes(output_path(action, "json", getattr(args, "output", None)), body)
    print(path)


def sanitized_status(document: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in document.items() if not key.startswith("location_")}
    available: dict[str, int] = {}
    for key, value in document.items():
        if not key.startswith("location_") or not value:
            continue
        name = key.removeprefix("location_").lower()
        available[name] = len(value) if isinstance(value, list) else 1
    if available:
        result["available_files"] = available
    return result


def poll_status(kind: str, identifier: str, timeout: int, *, sleeper: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    endpoint = f"{API_PREFIX}/{kind}/{quote(identifier, safe='')}/status"
    deadline = time.monotonic() + timeout
    delay = 2.0
    while True:
        document = api_json("GET", endpoint)
        status = str(document.get("status", ""))
        if status == "READY":
            return document
        if status == "FAILED":
            raise CliError(f"Moloco {kind[:-1]} generation failed")
        if time.monotonic() >= deadline:
            raise CliError(f"timed out waiting for Moloco {kind[:-1]} generation")
        sleeper(delay)
        delay = min(delay * 2, 30.0)


def validate_download_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise CliError("Moloco returned an invalid HTTPS download location")


def download_location(
    url: str,
    label: str,
    *,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> ApiResponse:
    validate_download_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    return perform_request(
        request,
        label,
        [],
        retry_safe=True,
        opener=opener,
        sleeper=sleeper,
    )


def download_files(
    status: Mapping[str, Any],
    file_format: str,
    action: str,
    selected_output: str | None,
) -> list[Path]:
    key = f"location_{file_format.lower()}"
    value = status.get(key)
    locations = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    if not locations:
        raise CliError(f"Moloco status did not include a {file_format.upper()} download")
    paths: list[Path] = []
    for index, location in enumerate(locations, start=1):
        assert isinstance(location, str)
        response = download_location(location, f"{action} download")
        if not response.body:
            raise CliError(f"Moloco returned an empty {file_format.upper()} download")
        path_suffixes = Path(urlparse(location).path).suffixes
        known_suffixes = [suffix.lstrip(".").lower() for suffix in path_suffixes]
        if known_suffixes and known_suffixes[-1] == "gz" and len(known_suffixes) >= 2:
            extension = f"{known_suffixes[-2]}.gz"
        else:
            extension = file_format.lower()
        if selected_output:
            base = Path(selected_output).expanduser()
            if len(locations) == 1:
                path = base
            else:
                suffix = base.suffix or f".{extension}"
                path = base.with_name(f"{base.stem}-{index:03d}{suffix}")
        else:
            path = output_path(f"{action}-{index:03d}" if len(locations) > 1 else action, extension)
        paths.append(write_bytes(path, response.body))
    return paths


def analytics_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = load_json_object(args.payload_file, args.payload_json, "payload")
    if args.ad_account_id:
        payload["ad_account_id"] = args.ad_account_id
    if args.from_date or args.to_date:
        if not args.from_date or not args.to_date:
            raise CliError("use --from and --to together")
        payload["date_range"] = {"start": args.from_date, "end": args.to_date}
    if args.dimensions:
        payload["dimensions"] = args.dimensions
    if args.metrics:
        payload["metrics"] = args.metrics
    if args.timezone:
        payload["timezone"] = args.timezone
    if args.limit is not None:
        if args.limit > MAX_ANALYTICS_ROWS:
            raise CliError(f"--limit must not exceed {MAX_ANALYTICS_ROWS}")
        payload["limit"] = str(args.limit)

    require_query(payload, ("ad_account_id", "date_range", "dimensions", "metrics"), "analytics")
    date_range = payload.get("date_range")
    if not isinstance(date_range, dict) or not date_range.get("start") or not date_range.get("end"):
        raise CliError("analytics date_range must contain start and end")
    try:
        validate_date_range(str(date_range["start"]), str(date_range["end"]), MAX_ANALYTICS_DAYS)
    except ValueError as exc:
        raise CliError("analytics dates must use YYYY-MM-DD") from exc
    if not isinstance(payload.get("dimensions"), list) or not payload["dimensions"]:
        raise CliError("analytics dimensions must be a non-empty array")
    if not isinstance(payload.get("metrics"), list) or not payload["metrics"]:
        raise CliError("analytics metrics must be a non-empty array")
    if "limit" in payload:
        try:
            limit = int(payload["limit"])
        except (TypeError, ValueError) as exc:
            raise CliError("analytics limit must be an integer") from exc
        if limit < 1 or limit > MAX_ANALYTICS_ROWS:
            raise CliError(f"analytics limit must be between 1 and {MAX_ANALYTICS_ROWS}")
        payload["limit"] = str(limit)
    return payload


def command_analytics(args: argparse.Namespace) -> None:
    endpoint = f"{API_PREFIX}/{args.command}"
    document = api_json("POST", endpoint, body=analytics_payload(args), retry_safe=True)
    emit_json(document, args.command, args)


def report_payload(args: argparse.Namespace) -> dict[str, Any]:
    validate_date_range(args.from_date, args.to_date, MAX_REPORT_DAYS)
    dimensions = [value.upper() for value in args.dimensions]
    unknown = sorted(set(dimensions) - REPORT_DIMENSIONS)
    if unknown:
        raise CliError(f"unsupported Report dimensions: {', '.join(unknown)}")
    optional_metrics = [value.upper() for value in (args.optional_metrics or [])]
    unknown_metrics = sorted(set(optional_metrics) - REPORT_OPTIONAL_METRICS)
    if unknown_metrics:
        raise CliError(f"unsupported Report optional metrics: {', '.join(unknown_metrics)}")
    payload: dict[str, Any] = {
        "ad_account_id": args.ad_account_id,
        "date_range": {"start": args.from_date, "end": args.to_date},
        "dimensions": dimensions,
    }
    if args.product_id:
        payload["product_id"] = args.product_id
    if optional_metrics:
        payload["optional_metrics"] = optional_metrics
    return payload


def command_report_create(args: argparse.Namespace) -> None:
    if args.wait and args.stdout:
        raise CliError("--stdout is not supported for report downloads; use --output")
    document = api_json(
        "POST",
        f"{API_PREFIX}/reports",
        params={"ad_account_id": args.ad_account_id},
        body=report_payload(args),
        retry_safe=False,
    )
    report_id = document.get("id")
    result: dict[str, Any] = {"report_id": report_id}
    if args.wait:
        if not isinstance(report_id, str) or not report_id:
            raise CliError("Moloco report response did not contain an ID")
        status = poll_status("reports", report_id, args.poll_timeout)
        paths = download_files(status, args.format, f"report-{report_id}", args.output)
        result.update({"status": "READY", "format": args.format, "files": [str(path) for path in paths]})
        print(json.dumps(result, ensure_ascii=False))
        return
    emit_json(result, "report-create", args)


def command_status(args: argparse.Namespace, kind: str, identifier: str) -> None:
    endpoint = f"{API_PREFIX}/{kind}/{quote(identifier, safe='')}/status"
    document = api_json("GET", endpoint)
    emit_json(sanitized_status(document), f"{kind[:-1]}-status", args)


def command_download(args: argparse.Namespace, kind: str, identifier: str) -> None:
    endpoint = f"{API_PREFIX}/{kind}/{quote(identifier, safe='')}/status"
    status = poll_status(kind, identifier, args.poll_timeout) if args.wait else api_json("GET", endpoint)
    if status.get("status") != "READY":
        raise CliError(f"Moloco {kind[:-1]} is not ready; current status is {status.get('status', 'UNKNOWN')}")
    paths = download_files(status, args.format, f"{kind[:-1]}-{identifier}", args.output)
    print(json.dumps({"status": "READY", "format": args.format, "files": [str(path) for path in paths]}))


def command_log_create(args: argparse.Namespace) -> None:
    if args.wait and args.stdout:
        raise CliError("--stdout is not supported for log downloads; use --output")
    payload: dict[str, Any] = {
        "ad_account_id": args.ad_account_id,
        "type": args.type,
        "format": args.format,
        "date": args.date,
    }
    if args.skip_compression:
        payload["skip_compression"] = True
    document = api_json(
        "POST",
        f"{API_PREFIX}/logs",
        params={"ad_account_id": args.ad_account_id},
        body=payload,
        retry_safe=False,
    )
    log = document.get("log")
    log_id = log.get("id") if isinstance(log, dict) else None
    result: dict[str, Any] = {"log_id": log_id}
    if args.wait:
        if not isinstance(log_id, str) or not log_id:
            raise CliError("Moloco log response did not contain an ID")
        status = poll_status("logs", log_id, args.poll_timeout)
        paths = download_files(status, args.format.lower(), f"log-{log_id}", args.output)
        result.update({"status": "READY", "format": args.format, "files": [str(path) for path in paths]})
        print(json.dumps(result, ensure_ascii=False))
        return
    emit_json(result, "log-create", args)


def command_list(args: argparse.Namespace) -> None:
    resource = normalize_resource(args.resource)
    query = common_query(args)
    if resource != "ad-accounts":
        require_query(query, ("ad_account_id",), f"list {resource}")
    document = api_json("GET", RESOURCE_PATHS[resource], params=query)
    emit_json(document, f"list-{resource}", args)


def command_get(args: argparse.Namespace) -> None:
    resource = normalize_resource(args.resource)
    document = api_json("GET", item_endpoint(resource, args.id), params=common_query(args))
    emit_json(document, f"get-{resource}", args)


def mutation_preview(method: str, endpoint: str, query: Mapping[str, Any], payload: Mapping[str, Any] | None, current: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "preview": True,
        "method": method,
        "endpoint": endpoint,
        "query": redact_object(dict(query)),
    }
    if payload is not None:
        result["payload"] = redact_object(dict(payload))
    if current is not None:
        result["current"] = redact_object(dict(current))
    result["next_step"] = "Confirm the exact target and payload, then rerun with --execute"
    return result


def command_mutation(args: argparse.Namespace) -> None:
    resource = normalize_resource(args.resource)
    query = common_query(args)
    payload = None
    if args.command in {"create", "update"}:
        payload = load_json_object(args.payload_file, args.payload_json, "payload")
        if not payload:
            raise CliError(f"{args.command} requires --payload-file or --payload-json")
    if args.command == "create":
        require_query(query, CREATE_REQUIRED_QUERY[resource], f"create {resource}")
        endpoint = RESOURCE_PATHS[resource]
        method = "POST"
        current = None
    else:
        endpoint = item_endpoint(resource, args.id)
        method = "PUT" if args.command == "update" else "DELETE"
        current = api_json("GET", endpoint, params=query)

    if not args.execute:
        print(json.dumps(mutation_preview(method, endpoint, query, payload, current), indent=2, ensure_ascii=False))
        return

    response = api_json(method, endpoint, params=query, body=payload, retry_safe=False)
    result: dict[str, Any] = {"response": response}
    if current is not None:
        result["before"] = current
    if args.command == "update":
        result["after"] = api_json("GET", endpoint, params=query)
    emit_json(result, f"{args.command}-{resource}", args)


def command_check(args: argparse.Namespace) -> None:
    cached = read_cached_token()
    print(json.dumps({
        "python": sys.version.split()[0],
        "api_origin": API_ORIGIN,
        "api_version": api_version(),
        "api_key_configured": bool(os.environ.get("MOLOCO_ADS_API_KEY", "").strip()),
        "cached_token_valid": bool(cached),
    }, indent=2))


def command_auth_status(args: argparse.Namespace) -> None:
    print(json.dumps({
        "api_key_configured": bool(os.environ.get("MOLOCO_ADS_API_KEY", "").strip()),
        "cached_token_valid": bool(read_cached_token()),
        "api_version": api_version(),
    }, indent=2))


ACTION_DESCRIPTIONS = {
    "analytics-overview": "Synchronous overview analytics (read)",
    "analytics-detail": "Synchronous filtered analytics, up to 10,000 rows (read)",
    "analytics-skadnetwork": "Synchronous SKAdNetwork analytics (read)",
    "report-create": "Create an asynchronous CSV/JSON report export (read job)",
    "report-status": "Check report state without exposing download URLs (read)",
    "report-download": "Download a ready report without forwarding the bearer token (read)",
    "log-create": "Create an asynchronous event-log export; account enablement required (read job)",
    "log-status": "Check log state without exposing download URLs (read)",
    "log-download": "Download all ready log parts without forwarding the bearer token (read)",
    "list/get": "Read an allowlisted campaign-management resource",
    "create/update/delete": "Preview an entity mutation; --execute is required to apply it",
}


def command_list_actions(args: argparse.Namespace) -> None:
    print(json.dumps(ACTION_DESCRIPTIONS, indent=2))


def command_describe(args: argparse.Namespace) -> None:
    description = ACTION_DESCRIPTIONS.get(args.action)
    if description is None:
        raise CliError(f"unknown action {args.action!r}; run list-actions")
    print(json.dumps({"action": args.action, "description": description}, indent=2))


def add_output_args(parser: argparse.ArgumentParser, stdout: bool = True) -> None:
    parser.add_argument("--output", help="output file path")
    if stdout:
        parser.add_argument("--stdout", action="store_true", help="print complete JSON instead of saving it")


def add_payload_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--payload-file", help="JSON request body file")
    group.add_argument("--payload-json", help="inline JSON request body")


def add_query_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--params-file", help="JSON query-parameter file")
    group.add_argument("--params-json", help="inline JSON query parameters")
    parser.add_argument("--ad-account-id")
    parser.add_argument("--product-id")
    parser.add_argument("--campaign-id")
    parser.add_argument("--inquiry-option")
    parser.add_argument("--states", type=comma_values)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check")
    subparsers.add_parser("auth-status")
    subparsers.add_parser("list-actions")
    describe = subparsers.add_parser("describe")
    describe.add_argument("--action", required=True)

    for command in ("analytics-overview", "analytics-detail", "analytics-skadnetwork"):
        analytics = subparsers.add_parser(command)
        add_payload_args(analytics)
        analytics.add_argument("--ad-account-id")
        analytics.add_argument("--from", dest="from_date", type=iso_date)
        analytics.add_argument("--to", dest="to_date", type=iso_date)
        analytics.add_argument("--dimensions", type=comma_values)
        analytics.add_argument("--metrics", type=comma_values)
        analytics.add_argument("--timezone")
        analytics.add_argument("--limit", type=positive_int)
        add_output_args(analytics)

    report_create = subparsers.add_parser("report-create")
    report_create.add_argument("--ad-account-id", required=True)
    report_create.add_argument("--product-id")
    report_create.add_argument("--from", dest="from_date", type=iso_date, required=True)
    report_create.add_argument("--to", dest="to_date", type=iso_date, required=True)
    report_create.add_argument("--dimensions", type=comma_values, required=True)
    report_create.add_argument("--optional-metrics", type=comma_values)
    report_create.add_argument("--format", choices=("csv", "json"), default="json")
    report_create.add_argument("--wait", action="store_true")
    report_create.add_argument("--poll-timeout", type=positive_int, default=DEFAULT_POLL_TIMEOUT)
    add_output_args(report_create)

    report_status = subparsers.add_parser("report-status")
    report_status.add_argument("--report-id", required=True)
    add_output_args(report_status)

    report_download = subparsers.add_parser("report-download")
    report_download.add_argument("--report-id", required=True)
    report_download.add_argument("--format", choices=("csv", "json"), default="json")
    report_download.add_argument("--wait", action="store_true")
    report_download.add_argument("--poll-timeout", type=positive_int, default=DEFAULT_POLL_TIMEOUT)
    add_output_args(report_download, stdout=False)

    log_create = subparsers.add_parser("log-create")
    log_create.add_argument("--ad-account-id", required=True)
    log_create.add_argument("--date", type=iso_date, required=True)
    log_create.add_argument("--type", choices=tuple(sorted(LOG_TYPES)), required=True)
    log_create.add_argument("--format", choices=tuple(sorted(LOG_FORMATS)), default="CSV")
    log_create.add_argument("--skip-compression", action="store_true")
    log_create.add_argument("--wait", action="store_true")
    log_create.add_argument("--poll-timeout", type=positive_int, default=DEFAULT_POLL_TIMEOUT)
    add_output_args(log_create)

    log_status = subparsers.add_parser("log-status")
    log_status.add_argument("--log-id", required=True)
    add_output_args(log_status)

    log_download = subparsers.add_parser("log-download")
    log_download.add_argument("--log-id", required=True)
    log_download.add_argument("--format", choices=("csv", "avro"), default="csv")
    log_download.add_argument("--wait", action="store_true")
    log_download.add_argument("--poll-timeout", type=positive_int, default=DEFAULT_POLL_TIMEOUT)
    add_output_args(log_download, stdout=False)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--resource", required=True)
    add_query_args(list_parser)
    add_output_args(list_parser)

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("--resource", required=True)
    get_parser.add_argument("--id", required=True)
    add_query_args(get_parser)
    add_output_args(get_parser)

    for command in ("create", "update", "delete"):
        mutation = subparsers.add_parser(command)
        mutation.add_argument("--resource", required=True)
        if command != "create":
            mutation.add_argument("--id", required=True)
        if command != "delete":
            add_payload_args(mutation)
        add_query_args(mutation)
        mutation.add_argument("--execute", action="store_true")
        add_output_args(mutation)

    return parser


def run(args: argparse.Namespace) -> None:
    if args.command == "check":
        command_check(args)
    elif args.command == "auth-status":
        command_auth_status(args)
    elif args.command == "list-actions":
        command_list_actions(args)
    elif args.command == "describe":
        command_describe(args)
    elif args.command.startswith("analytics-"):
        command_analytics(args)
    elif args.command == "report-create":
        command_report_create(args)
    elif args.command == "report-status":
        command_status(args, "reports", args.report_id)
    elif args.command == "report-download":
        command_download(args, "reports", args.report_id)
    elif args.command == "log-create":
        command_log_create(args)
    elif args.command == "log-status":
        command_status(args, "logs", args.log_id)
    elif args.command == "log-download":
        command_download(args, "logs", args.log_id)
    elif args.command == "list":
        command_list(args)
    elif args.command == "get":
        command_get(args)
    elif args.command in {"create", "update", "delete"}:
        command_mutation(args)
    else:
        raise CliError(f"unsupported command {args.command}")


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        run(args)
        return 0
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
