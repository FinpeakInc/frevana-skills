#!/usr/bin/env python3

"""Safe direct client for TikTok Business API v1.3."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import ssl
import stat
import sys
import time
import webbrowser
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlencode, urlparse


API_HOST = "business-api.tiktok.com"
API_BASE_URL = f"https://{API_HOST}"
API_PREFIX = "/open_api/v1.3/"
AUTHORIZATION_BASE_URL = "https://ads.tiktok.com/marketing_api/auth"
DEFAULT_REDIRECT_URI = "http://localhost:51021/callback"

ACTIONS = {
    "advertisers": {
        "method": "GET",
        "path": f"{API_PREFIX}oauth2/advertiser/get/",
        "description": "Get advertisers authorized for the developer app.",
        "requires_app_credentials": True,
        "requires_access_token": False,
    },
    "account-get": {"method": "GET", "path": f"{API_PREFIX}advertiser/info/", "description": "Get ad account details."},
    "campaigns": {"method": "GET", "path": f"{API_PREFIX}campaign/get/", "description": "Get campaigns."},
    "campaign-create": {"method": "POST", "path": f"{API_PREFIX}campaign/create/", "description": "Create a campaign."},
    "campaign-update": {"method": "POST", "path": f"{API_PREFIX}campaign/update/", "description": "Update a campaign."},
    "campaign-status": {"method": "POST", "path": f"{API_PREFIX}campaign/status/update/", "description": "Update campaign statuses."},
    "adgroups": {"method": "GET", "path": f"{API_PREFIX}adgroup/get/", "description": "Get ad groups."},
    "adgroup-create": {"method": "POST", "path": f"{API_PREFIX}adgroup/create/", "description": "Create an ad group."},
    "adgroup-update": {"method": "POST", "path": f"{API_PREFIX}adgroup/update/", "description": "Update an ad group."},
    "adgroup-status": {"method": "POST", "path": f"{API_PREFIX}adgroup/status/update/", "description": "Update ad group statuses."},
    "ads": {"method": "GET", "path": f"{API_PREFIX}ad/get/", "description": "Get ads."},
    "ad-create": {"method": "POST", "path": f"{API_PREFIX}ad/create/", "description": "Create an ad."},
    "ad-update": {"method": "POST", "path": f"{API_PREFIX}ad/update/", "description": "Update an ad."},
    "ad-status": {"method": "POST", "path": f"{API_PREFIX}ad/status/update/", "description": "Update ad statuses."},
    "report": {"method": "GET", "path": f"{API_PREFIX}report/integrated/get/", "description": "Run a synchronous report."},
}

SECRET_KEYS = {"access_token", "refresh_token", "secret", "app_secret", "client_secret", "token", "authorization"}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
FILE_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class CliError(Exception):
    pass


def redact(value: Any, key: str | None = None) -> Any:
    if key and (key.lower() in SECRET_KEYS or "secret" in key.lower() or "token" in key.lower()):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def write_json_securely(path_value: str, value: Any) -> None:
    target = Path(path_value).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        info = target.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise CliError(f"Output must be a regular non-symlink file: {target}")
        if info.st_uid != os.getuid():
            raise CliError(f"Output file must be owned by the current user: {target}")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise CliError(f"Existing output file must not be group- or world-accessible: {target}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(target, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def print_json(value: Any, output: str | None = None, display_value: Any | None = None) -> None:
    if output:
        write_json_securely(output, value)
    displayed = value if display_value is None else display_value
    print(json.dumps(displayed, indent=2, ensure_ascii=False, sort_keys=True))


def read_secret_file(path_value: str, label: str) -> str:
    path = Path(path_value).expanduser()
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise CliError(f"{label} file does not exist: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise CliError(f"{label} file must be a regular non-symlink file: {path}")
    if info.st_uid != os.getuid():
        raise CliError(f"{label} file must be owned by the current user: {path}")
    mode = stat.S_IMODE(info.st_mode)
    if mode not in {0o400, 0o600}:
        raise CliError(f"{label} file must have mode 0400 or 0600, found {mode:04o}: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise CliError(f"{label} file is empty: {path}")
    return value


def default_credentials_file() -> Path:
    override = os.environ.get("TIKTOK_ADS_CREDENTIALS_FILE")
    if override:
        return Path(override).expanduser()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return config_home / "tiktok-ads" / "credentials.json"


def credentials_file_for(args: argparse.Namespace) -> Path:
    value = getattr(args, "credentials_file", None)
    return Path(value).expanduser() if value else default_credentials_file()


def load_credentials(path: Path, required: bool = False) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        if required:
            raise CliError(f"TikTok Ads credentials file does not exist: {path}")
        return {}
    try:
        value = json.loads(read_secret_file(str(path), "credentials"))
    except json.JSONDecodeError as exc:
        raise CliError(f"TikTok Ads credentials file is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CliError(f"TikTok Ads credentials file must contain a JSON object: {path}")
    return value


def read_access_token_file(path_value: str) -> str:
    raw = read_secret_file(path_value, "access token")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(value, dict) and isinstance(value.get("access_token"), str) and value["access_token"].strip():
        return value["access_token"].strip()
    raise CliError("Access token JSON file must contain a non-empty access_token field")


def load_params(args: argparse.Namespace) -> dict[str, Any]:
    if args.params_json and args.params_file:
        raise CliError("Use only one of --params-json and --params-file")
    if args.params_file:
        try:
            raw = Path(args.params_file).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise CliError(f"Cannot read params file: {args.params_file}") from exc
    else:
        raw = args.params_json or "{}"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(f"Parameters are not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CliError("Parameters must be a JSON object")
    return value


def resolve_access_token(args: argparse.Namespace) -> str:
    if getattr(args, "access_token_file", None):
        token = read_access_token_file(args.access_token_file)
    else:
        token = os.environ.get("TIKTOK_ADS_ACCESS_TOKEN", "")
        if not token:
            token = str(load_credentials(credentials_file_for(args)).get("access_token") or "")
    if not token:
        raise CliError("Missing access token; run authorize, set TIKTOK_ADS_ACCESS_TOKEN, or use --access-token-file")
    return token


def resolve_app_id(args: argparse.Namespace) -> str:
    value = getattr(args, "app_id", None) or os.environ.get("TIKTOK_ADS_APP_ID")
    if not value:
        value = load_credentials(credentials_file_for(args)).get("app_id")
    if not value:
        raise CliError("Missing app ID; use --app-id, set TIKTOK_ADS_APP_ID, or run authorize")
    return str(value)


def resolve_app_secret(args: argparse.Namespace) -> str:
    path = getattr(args, "app_secret_file", None)
    value = read_secret_file(path, "app secret") if path else os.environ.get("TIKTOK_ADS_APP_SECRET", "")
    if not value:
        raise CliError("Missing app secret; set TIKTOK_ADS_APP_SECRET or use --app-secret-file")
    return value


def encode_query_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def validate_api_path(path: str) -> str:
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise CliError("API path must be a path only, without host, query, or fragment")
    decoded = unquote(path)
    if any(ord(character) < 32 or ord(character) == 127 for character in decoded):
        raise CliError("API path must not contain control characters")
    if not decoded.startswith(API_PREFIX) or ".." in decoded or "//" in decoded or "\\" in decoded:
        raise CliError(f"API path must remain under {API_PREFIX}")
    return path


def parse_file_arguments(values: list[str]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for item in values:
        if "=" not in item:
            raise CliError("--file must use FIELD=/absolute/or/relative/path")
        field, path_value = item.split("=", 1)
        if not FILE_FIELD.fullmatch(field) or field in files:
            raise CliError(f"Invalid or duplicate multipart field: {field}")
        path = Path(path_value).expanduser()
        try:
            info = path.lstat()
        except FileNotFoundError as exc:
            raise CliError(f"Upload file does not exist: {path}") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise CliError(f"Upload must be a regular non-symlink file: {path}")
        if any(character in path.name for character in ('"', "\r", "\n")):
            raise CliError(f"Upload filename contains unsupported header characters: {path.name}")
        files[field] = path
    return files


def decode_response(status: int, body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = {"http_status": status, "raw_body": text[:2000]}
    if not isinstance(value, dict):
        value = {"http_status": status, "data": value}
    if status < 200 or status >= 300:
        raise CliError(f"TikTok HTTP request failed: status={status} response={json.dumps(redact(value), ensure_ascii=False)}")
    return value


def send_multipart(
    method: str,
    path: str,
    params: dict[str, Any],
    files: dict[str, Path],
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    if method != "POST":
        raise CliError("Multipart uploads currently require POST")
    boundary = f"tiktok-ads-{secrets.token_hex(16)}"
    chunks: list[bytes | tuple[Path, int]] = []
    for name, value in params.items():
        if not FILE_FIELD.fullmatch(str(name)):
            raise CliError(f"Invalid multipart parameter field: {name}")
        payload = encode_query_value(value).encode("utf-8")
        chunks.extend([
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode(),
            payload,
            b"\r\n",
        ])
    for field, file_path in files.items():
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        header = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{file_path.name}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        chunks.extend([header, (file_path, file_path.stat().st_size), b"\r\n"])
    chunks.append(f"--{boundary}--\r\n".encode())
    content_length = sum(len(item) if isinstance(item, bytes) else item[1] for item in chunks)
    connection = http.client.HTTPSConnection(API_HOST, timeout=timeout, context=ssl.create_default_context())
    try:
        connection.putrequest(method, path)
        for key, value in headers.items():
            connection.putheader(key, value)
        connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        connection.putheader("Content-Length", str(content_length))
        connection.endheaders()
        for item in chunks:
            if isinstance(item, bytes):
                connection.send(item)
            else:
                with item[0].open("rb") as stream:
                    while True:
                        block = stream.read(1024 * 1024)
                        if not block:
                            break
                        connection.send(block)
        response = connection.getresponse()
        return decode_response(response.status, response.read())
    except OSError as exc:
        raise CliError(f"TikTok API network request failed: {exc}") from exc
    finally:
        connection.close()


def api_request(
    method: str,
    path: str,
    params: dict[str, Any],
    access_token: str | None,
    timeout: int = 180,
    files: dict[str, Path] | None = None,
) -> dict[str, Any]:
    method = method.upper()
    if method not in HTTP_METHODS:
        raise CliError(f"Unsupported HTTP method: {method}")
    path = validate_api_path(path)
    headers = {"Accept": "application/json", "User-Agent": "frevana-tiktok-ads-skill/1.0"}
    if access_token:
        headers["Access-Token"] = access_token
    if files:
        return send_multipart(method, path, params, files, headers, timeout)
    body = None
    if method == "GET":
        query = urlencode({key: encode_query_value(value) for key, value in params.items()})
        if query:
            path = f"{path}?{query}"
    else:
        body = json.dumps(params, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    connection = http.client.HTTPSConnection(API_HOST, timeout=timeout, context=ssl.create_default_context())
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return decode_response(response.status, response.read())
    except OSError as exc:
        raise CliError(f"TikTok API network request failed: {exc}") from exc
    finally:
        connection.close()


def has_tiktok_error(value: dict[str, Any]) -> bool:
    return value.get("code") not in {None, 0, "0"}


def validate_redirect_uri(redirect_uri: str) -> Any:
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise CliError("Local OAuth redirect URI must use http://localhost or http://127.0.0.1")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CliError("Local OAuth redirect URI must not contain user info, query parameters, or a fragment")
    if parsed.port is None or not (1 <= parsed.port <= 65535):
        raise CliError("Local OAuth redirect URI must include a valid port")
    if not parsed.path.startswith("/") or parsed.path == "/":
        raise CliError("Local OAuth redirect URI must include a callback path such as /callback")
    return parsed


def build_authorization_url(app_id: str, redirect_uri: str, state: str, scope: str | None = None) -> str:
    validate_redirect_uri(redirect_uri)
    query = {"app_id": app_id, "state": state, "redirect_uri": redirect_uri}
    if scope:
        query["scope"] = scope
    return f"{AUTHORIZATION_BASE_URL}?{urlencode(query)}"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    server_version = "TikTokAdsOAuth/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_page(self, status: int, title: str, message: str) -> None:
        body = f"<!doctype html><meta charset='utf-8'><title>{title}</title><h1>{title}</h1><p>{message}</p>".encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        server = self.server
        parsed = urlparse(self.path)
        if parsed.path != server.callback_path:
            self.send_page(404, "Not Found", "This server only accepts the configured TikTok OAuth callback.")
            return
        query = parse_qs(parsed.query, keep_blank_values=True)
        received_state = query.get("state", [""])[0]
        if not secrets.compare_digest(received_state, server.expected_state):
            server.callback_result = {
                "error": "state_mismatch",
                "error_description": "OAuth state did not match.",
            }
            self.send_page(400, "Authorization rejected", "OAuth state did not match. Return to TikTok and try again.")
            return
        error = query.get("error", [""])[0]
        if error:
            server.callback_result = {"error": error, "error_description": query.get("error_description", [""])[0]}
            self.send_page(400, "Authorization failed", "TikTok returned an authorization error. You may close this window.")
            return
        auth_code = query.get("auth_code", [""])[0]
        if not auth_code:
            server.callback_result = {
                "error": "missing_auth_code",
                "error_description": "The callback did not contain auth_code.",
            }
            self.send_page(400, "Authorization rejected", "The callback did not contain auth_code.")
            return
        server.callback_result = {"auth_code": auth_code}
        self.send_page(200, "TikTok authorization received", "The authorization code was received. You may close this window.")


def wait_for_oauth_callback(
    redirect_uri: str,
    state: str,
    timeout_seconds: int,
    ready: Callable[[], None] | None = None,
    server_factory: Any = ThreadingHTTPServer,
) -> str:
    parsed = validate_redirect_uri(redirect_uri)
    try:
        server = server_factory((parsed.hostname, parsed.port), OAuthCallbackHandler)
    except OSError as exc:
        raise CliError(f"Cannot start local OAuth callback server on {parsed.hostname}:{parsed.port}: {exc}") from exc
    server.callback_path = parsed.path
    server.expected_state = state
    server.callback_result = None
    server.timeout = 1
    if ready:
        ready()
    deadline = time.monotonic() + timeout_seconds
    try:
        while server.callback_result is None and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if server.callback_result is None:
        raise CliError(f"Timed out after {timeout_seconds} seconds waiting for the TikTok OAuth callback")
    if "error" in server.callback_result:
        description = server.callback_result.get("error_description") or "no description"
        raise CliError(f"TikTok authorization failed: {server.callback_result['error']} ({description})")
    return server.callback_result["auth_code"]


def exchange_auth_code(app_id: str, app_secret: str, auth_code: str, timeout: int = 180) -> dict[str, Any]:
    result = api_request(
        "POST",
        f"{API_PREFIX}oauth2/access_token/",
        {"app_id": app_id, "auth_code": auth_code, "secret": app_secret},
        access_token=None,
        timeout=timeout,
    )
    if has_tiktok_error(result):
        raise CliError(f"TikTok token exchange failed: code={result.get('code')} message={result.get('message') or result.get('msg')}")
    data = result.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("access_token"), str) or not data["access_token"]:
        raise CliError("TikTok token exchange response did not contain data.access_token")
    return data


def refresh_short_term_token(
    app_id: str,
    app_secret: str,
    refresh_token: str,
    timeout: int = 180,
) -> dict[str, Any]:
    result = api_request(
        "POST",
        f"{API_PREFIX}tt_user/oauth2/refresh_token/",
        {
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        access_token=None,
        timeout=timeout,
    )
    if has_tiktok_error(result):
        raise CliError(
            f"TikTok token refresh failed: code={result.get('code')} "
            f"message={result.get('message') or result.get('msg')}"
        )
    data = result.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("access_token"), str) or not data["access_token"]:
        raise CliError("TikTok token refresh response did not contain data.access_token")
    return data


def token_expiry_metadata(token_data: dict[str, Any], now: datetime | None = None) -> dict[str, str]:
    current = now or datetime.now(timezone.utc)
    metadata: dict[str, str] = {}
    for seconds_key, timestamp_key in (
        ("expires_in", "access_token_expires_at"),
        ("refresh_token_expires_in", "refresh_token_expires_at"),
    ):
        value = token_data.get(seconds_key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            metadata[timestamp_key] = (current + timedelta(seconds=value)).isoformat()
    return metadata


def command_authorize(args: argparse.Namespace) -> int:
    app_id = resolve_app_id(args)
    app_secret = resolve_app_secret(args)
    if not (30 <= args.timeout <= 1800):
        raise CliError("--timeout must be between 30 and 1800 seconds")
    state = secrets.token_urlsafe(32)
    authorization_url = build_authorization_url(app_id, args.redirect_uri, state, args.scope)

    def show_ready() -> None:
        print_json({
            "authorization_url": authorization_url,
            "redirect_uri": args.redirect_uri,
            "callback_server": "listening",
            "timeout_seconds": args.timeout,
            "note": "Opening authorization_url in browser. If the browser does not open, copy the URL below and open it manually.",
        })
        print(f"\nAuthorization URL:\n{authorization_url}\n", flush=True)
        try:
            webbrowser.open(authorization_url)
        except Exception:  # noqa: BLE001
            pass  # Best-effort; user can open the URL manually if this fails

    auth_code = wait_for_oauth_callback(args.redirect_uri, state, args.timeout, ready=show_ready)
    token_data = exchange_auth_code(app_id, app_secret, auth_code, timeout=args.request_timeout)
    credentials = dict(token_data)
    credentials["app_id"] = app_id
    credentials["authorized_at"] = datetime.now(timezone.utc).isoformat()
    credentials.update(token_expiry_metadata(token_data))
    if args.scope:
        credentials["requested_scope"] = args.scope
    target = credentials_file_for(args)
    write_json_securely(str(target), credentials)
    print("\nAuthorization complete. Saving credentials...\n", flush=True)
    print_json({
        "ok": True,
        "credentials_file": str(target),
        "credentials": redact(credentials),
        "note": "Access token saved with mode 0600. App secret was not saved.",
    })
    return 0


def command_refresh_token(args: argparse.Namespace) -> int:
    if not (1 <= args.request_timeout <= 600):
        raise CliError("--request-timeout must be between 1 and 600 seconds")
    target = credentials_file_for(args)
    credentials = load_credentials(target, required=True)
    refresh_token = credentials.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise CliError(
            "Saved credentials do not contain a refresh_token. Long-term Marketing API tokens do not use "
            "refresh tokens; reauthorize if that token is invalid."
        )
    app_id = resolve_app_id(args)
    app_secret = resolve_app_secret(args)
    token_data = refresh_short_term_token(
        app_id,
        app_secret,
        refresh_token,
        timeout=args.request_timeout,
    )
    refreshed_at = datetime.now(timezone.utc)
    updated = dict(credentials)
    updated.update(token_data)
    # Some providers rotate the refresh token, while others omit it when it is unchanged.
    updated.setdefault("refresh_token", refresh_token)
    updated["app_id"] = app_id
    updated["refreshed_at"] = refreshed_at.isoformat()
    updated.update(token_expiry_metadata(token_data, now=refreshed_at))
    write_json_securely(str(target), updated)
    print_json({
        "ok": True,
        "credentials_file": str(target),
        "credentials": redact(updated),
        "note": "Short-term access token refreshed and credentials updated with mode 0600. App secret was not saved.",
    })
    return 0


def command_auth_status(args: argparse.Namespace) -> None:
    target = credentials_file_for(args)
    credentials = load_credentials(target, required=True)
    print_json({
        "configured": bool(credentials.get("access_token")),
        "credentials_file": str(target),
        "app_id": credentials.get("app_id"),
        "authorized_at": credentials.get("authorized_at"),
        "refreshed_at": credentials.get("refreshed_at"),
        "access_token": "[PRESENT]" if credentials.get("access_token") else "[MISSING]",
        "access_token_expires_at": credentials.get("access_token_expires_at"),
        "refresh_token": "[PRESENT]" if credentials.get("refresh_token") else "[MISSING]",
        "refresh_token_expires_at": credentials.get("refresh_token_expires_at"),
        "advertiser_ids": credentials.get("advertiser_ids"),
        "scope": credentials.get("scope") or credentials.get("requested_scope"),
    })


def resolve_operation(args: argparse.Namespace) -> tuple[str, str, str, bool, bool]:
    if args.action:
        if args.method or args.path:
            raise CliError("Use --action or --method/--path, not both")
        spec = ACTIONS[args.action]
        return (
            spec["method"],
            spec["path"],
            spec["description"],
            bool(spec.get("requires_app_credentials")),
            bool(spec.get("requires_access_token", True)),
        )
    if not args.method or not args.path:
        raise CliError("call requires --action or both --method and --path")
    method = args.method.upper()
    validate_api_path(args.path)
    return method, args.path, "Custom TikTok Business API v1.3 request.", False, True


def command_call(args: argparse.Namespace) -> int:
    method, path, description, requires_app_credentials, requires_access_token = resolve_operation(args)
    if not (1 <= args.request_timeout <= 600):
        raise CliError("--request-timeout must be between 1 and 600 seconds")
    params = load_params(args)
    if requires_app_credentials:
        params.setdefault("app_id", resolve_app_id(args))
        params.setdefault("secret", resolve_app_secret(args))
    files = parse_file_arguments(args.file)
    mutation = method != "GET"
    preview = {
        "executed": False,
        "operation": {"method": method, "url": f"{API_BASE_URL}{path}", "description": description, "mutation": mutation},
        "params": redact(params),
        "files": {name: str(path_value) for name, path_value in files.items()},
        "requires_execute": mutation,
    }
    if args.dry_run or (mutation and not args.execute):
        print_json(preview, args.output)
        return 0
    token = resolve_access_token(args) if requires_access_token else None
    result = api_request(method, path, params, token, timeout=args.request_timeout, files=files)
    print_json(result, args.output, display_value=redact(result))
    return 2 if has_tiktok_error(result) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safely call TikTok Business API v1.3 directly")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="show the fixed official API target and Python runtime")
    subparsers.add_parser("list-actions", help="list built-in action aliases")

    describe = subparsers.add_parser("describe", help="describe a built-in action")
    describe.add_argument("--action", required=True, choices=sorted(ACTIONS))

    authorize = subparsers.add_parser("authorize", help="obtain an access token through a local OAuth callback server")
    authorize.add_argument("--app-id")
    authorize.add_argument("--app-secret-file")
    authorize.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI)
    authorize.add_argument("--scope")
    authorize.add_argument("--timeout", type=int, default=300)
    authorize.add_argument("--request-timeout", type=int, default=180)
    authorize.add_argument("--credentials-file")

    auth_status = subparsers.add_parser("auth-status", help="inspect saved authorization without exposing tokens")
    auth_status.add_argument("--credentials-file")

    refresh_token = subparsers.add_parser(
        "refresh-token",
        help="renew a saved short-term TikTok account access token with its refresh token",
    )
    refresh_token.add_argument("--app-id")
    refresh_token.add_argument("--app-secret-file")
    refresh_token.add_argument("--credentials-file")
    refresh_token.add_argument("--request-timeout", type=int, default=180)

    call = subparsers.add_parser("call", help="preview or execute a TikTok Business API request")
    call.add_argument("--action", choices=sorted(ACTIONS))
    call.add_argument("--method", choices=sorted(HTTP_METHODS))
    call.add_argument("--path")
    call.add_argument("--params-json")
    call.add_argument("--params-file")
    call.add_argument("--file", action="append", default=[], metavar="FIELD=PATH")
    call.add_argument("--access-token-file")
    call.add_argument("--app-id")
    call.add_argument("--app-secret-file")
    call.add_argument("--credentials-file")
    call.add_argument("--request-timeout", type=int, default=180)
    call.add_argument("--output")
    call.add_argument("--dry-run", action="store_true")
    call.add_argument("--execute", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "check":
            print_json({"ok": True, "api_base_url": API_BASE_URL, "api_version": "v1.3", "python": sys.version.split()[0]})
        elif args.command == "list-actions":
            print_json({"actions": ACTIONS})
        elif args.command == "describe":
            print_json({"action": args.action, **ACTIONS[args.action]})
        elif args.command == "authorize":
            return command_authorize(args)
        elif args.command == "auth-status":
            command_auth_status(args)
        elif args.command == "refresh-token":
            return command_refresh_token(args)
        elif args.command == "call":
            return command_call(args)
        return 0
    except CliError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "error": "Interrupted"}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
