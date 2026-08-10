#!/usr/bin/env python3
"""Safe, dependency-free CLI for the Mintegral AppGrowth Open API."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import stat
import sys
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_HOST = "https://ss-api.mintegral.com"
STORAGE_HOST = "https://ss-storage-api.mintegral.com"
SENSITIVE_KEYS = {"access-key", "access_key", "api_key", "token", "authorization"}


class CliError(RuntimeError):
    pass


class RejectRedirects(HTTPRedirectHandler):
    """Reject redirects so signed headers never leave the fixed API host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


HTTP_OPENER = build_opener(RejectRedirects())


def open_request(request: Request, *, timeout: int):
    return HTTP_OPENER.open(request, timeout=timeout)


@dataclass(frozen=True)
class Action:
    method: str
    path: str
    description: str
    required: tuple[str, ...] = ()
    mutation: bool = False
    preflight: str | None = None
    full_replacement: bool = False
    destructive: bool = False
    storage: bool = False
    multipart: bool = False


ACTIONS: dict[str, Action] = {
    "balance": Action("GET", "/api/open/v1/account/balance", "Read account balance"),
    "campaigns": Action("GET", "/api/open/v1/campaign", "List campaigns"),
    "offers": Action("GET", "/api/open/v1/offers", "List offers"),
    "creative-sets": Action("GET", "/api/open/v1/creative_sets", "List creative sets"),
    "report": Action("GET", "/api/v1/reports/data", "Read performance report"),
    "campaign-create": Action("POST", "/api/open/v1/campaign", "Create campaign", ("campaign_name", "promotion_type", "preview_url"), True),
    "campaign-update": Action("PUT", "/api/open/v1/campaign", "Update campaign", ("campaign_id",), True, "campaign"),
    "offer-create": Action("POST", "/api/open/v1/offer", "Create offer", ("campaign_id", "offer_name"), True, "campaign"),
    "offer-update": Action("PUT", "/api/open/v1/offer", "Update offer", ("offer_id",), True, "offer"),
    "offer-bid": Action("PUT", "/api/open/v1/offer/bid_rate", "Replace offer bids", ("offer_id",), True, "offer", True),
    "offer-budget": Action("PUT", "/api/open/v1/offer/budget", "Replace offer budgets", ("offer_id", "budget"), True, "offer", True),
    "offer-status": Action("PUT", "/api/open/v1/offer/status", "Start or stop offer", ("offer_id", "status"), True, "offer"),
    "publisher-target": Action("PUT", "/api/open/v1/offer/target", "Replace publisher targeting", ("offer_id", "option"), True, "offer", True),
    "tracking-update": Action("PUT", "/api/open/v1/tracking", "Update tracking URLs", ("offer_id", "tracking_method"), True, "offer"),
    "audience-target": Action("PUT", "/api/open/v1/offer/target-audience", "Update audience targeting", ("offer_id", "include_ta_id", "exclude_ta_id"), True, "offer"),
    "target-goal": Action("PUT", "/api/open/v3/offer/target_goal", "Update optimization goal", ("offer_id",), True, "offer"),
    "creative-set-create": Action("POST", "/api/open/v1/creative_set", "Create creative set", ("creative_set_name", "ad_outputs", "creatives"), True, "offer"),
    "creative-set-update": Action("PUT", "/api/open/v1/creative_set", "Update creative set", ("offer_id", "creative_set_name"), True, "creative-set"),
    "creative-set-delete": Action("DELETE", "/api/open/v1/creative_set", "Delete creative set", ("offer_id", "creative_set_name"), True, "creative-set", False, True),
    "creative-upload": Action("POST", "/api/open/v1/creatives/upload", "Upload image or video creative", mutation=True, storage=True, multipart=True),
    "playable-upload": Action("POST", "/api/open/v1/playable/upload", "Upload playable creative", mutation=True, storage=True, multipart=True),
}


def compute_token(api_key: str, timestamp: int) -> str:
    inner = hashlib.md5(str(timestamp).encode("utf-8")).hexdigest()
    return hashlib.md5((api_key + inner).encode("utf-8")).hexdigest()


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if key.lower() in SENSITIVE_KEYS else redact(item, secrets)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        result = value
        for secret in secrets:
            if secret:
                result = result.replace(secret, "[REDACTED]")
        return result
    return value


def credentials() -> tuple[str, str]:
    access_key = os.environ.get("MINTEGRAL_ACCESS_KEY", "")
    api_key = os.environ.get("MINTEGRAL_API_KEY", "")
    missing = [name for name, value in (("MINTEGRAL_ACCESS_KEY", access_key), ("MINTEGRAL_API_KEY", api_key)) if not value]
    if missing:
        raise CliError("Missing " + ", ".join(missing) + ". Export credentials obtained from Mintegral Account > Basic Information.")
    return access_key, api_key


def load_params(args: argparse.Namespace) -> dict[str, Any]:
    if args.params_json and args.params_file:
        raise CliError("Use only one of --params-json or --params-file")
    raw = "{}"
    if args.params_json:
        raw = args.params_json
    elif args.params_file:
        path = Path(args.params_file).expanduser()
        if not path.is_file() or path.is_symlink():
            raise CliError("--params-file must be a regular, non-symlink file")
        file_stat = path.stat()
        if hasattr(os, "getuid") and file_stat.st_uid != os.getuid():
            raise CliError("--params-file must be owned by the current user")
        mode = stat.S_IMODE(file_stat.st_mode)
        if mode & 0o077:
            raise CliError("--params-file must not be accessible by group or other users; use mode 0600")
        raw = path.read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(f"Invalid JSON payload: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise CliError("Request parameters must be a JSON object")
    return value


def validate_payload(name: str, action: Action, params: dict[str, Any]) -> None:
    missing = [field for field in action.required if field not in params]
    if missing:
        raise CliError("Missing required payload fields: " + ", ".join(missing))
    if name == "offer-status" and params.get("status") not in {"RUNNING", "STOPPED"}:
        raise CliError("offer-status requires status RUNNING or STOPPED")
    if name == "publisher-target" and params.get("option") not in {"ENABLE", "DISABLE", "ALLOW_ALL"}:
        raise CliError("publisher-target requires option ENABLE, DISABLE, or ALLOW_ALL")
    if name == "campaign-create" and params.get("promotion_type") not in {"APP", "WEBSITE"}:
        raise CliError("campaign-create requires promotion_type APP or WEBSITE")
    if name == "offer-budget" and not isinstance(params.get("budget"), list):
        raise CliError("offer-budget requires budget to be an array containing the complete configuration")
    for key in ("include_ta_id", "exclude_ta_id"):
        if name == "audience-target" and not isinstance(params.get(key), list):
            raise CliError(f"audience-target requires {key} to be an array")


def auth_headers(access_key: str, api_key: str, content_type: str | None = "application/json") -> dict[str, str]:
    timestamp = int(time.time())
    headers = {
        "Accept": "application/json",
        "access-key": access_key,
        "timestamp": str(timestamp),
        "token": compute_token(api_key, timestamp),
        "User-Agent": "frevana-mintegral-ads/1.0",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def query_string(params: dict[str, Any]) -> str:
    normalized: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, list):
            normalized[key] = ",".join(str(item) for item in value)
        elif isinstance(value, (dict, tuple)):
            normalized[key] = json.dumps(value, separators=(",", ":"))
        else:
            normalized[key] = value
    return urlencode(normalized)


def request_json(action: Action, params: dict[str, Any], *, retries: int | None = None) -> dict[str, Any]:
    access_key, api_key = credentials()
    host = STORAGE_HOST if action.storage else API_HOST
    url = host + action.path
    data: bytes | None = None
    if action.method == "GET":
        encoded = query_string(params)
        if encoded:
            url += "?" + encoded
    else:
        data = json.dumps(params, separators=(",", ":")).encode("utf-8")
    attempts = retries if retries is not None else (3 if action.method == "GET" else 1)
    last_error: Exception | None = None
    for attempt in range(attempts):
        req = Request(url, data=data, headers=auth_headers(access_key, api_key), method=action.method)
        try:
            with open_request(req, timeout=60) as response:
                raw = response.read().decode("utf-8", "replace")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise CliError("Mintegral returned a non-object JSON response")
            if str(result.get("code")) != "200":
                safe = redact(result, (access_key, api_key))
                raise CliError("Mintegral API error: " + json.dumps(safe, ensure_ascii=False))
            return result
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            safe_body = redact(body, (access_key, api_key))
            last_error = CliError(f"Mintegral HTTP {exc.code}: {safe_body}")
            if action.method != "GET" or exc.code not in {429, 500, 502, 503, 504} or attempt + 1 >= attempts:
                raise last_error
        except (URLError, TimeoutError) as exc:
            last_error = CliError(f"Mintegral network error: {redact(str(exc), (access_key, api_key))}")
            if action.method != "GET" or attempt + 1 >= attempts:
                raise last_error
        except json.JSONDecodeError as exc:
            raise CliError("Mintegral returned invalid JSON") from exc
        time.sleep(min(2**attempt, 4))
    raise last_error or CliError("Request failed")


def multipart_body(file_path: Path) -> tuple[bytes, str]:
    if not file_path.is_file() or file_path.is_symlink():
        raise CliError("--file must be a regular, non-symlink file")
    if file_path.stat().st_size > 250 * 1024 * 1024:
        raise CliError("Refusing to load an upload larger than 250 MiB")
    boundary = "----frevana-" + uuid.uuid4().hex
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    safe_name = file_path.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    return prefix + file_path.read_bytes() + suffix, f"multipart/form-data; boundary={boundary}"


def upload(action: Action, file_path: Path) -> dict[str, Any]:
    access_key, api_key = credentials()
    body, content_type = multipart_body(file_path)
    req = Request(
        STORAGE_HOST + action.path,
        data=body,
        headers=auth_headers(access_key, api_key, content_type),
        method="POST",
    )
    try:
        with open_request(req, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8", "replace"))
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", "replace")
        raise CliError(f"Mintegral upload HTTP {exc.code}: {redact(body_text, (access_key, api_key))}") from exc
    except (URLError, TimeoutError) as exc:
        raise CliError(f"Mintegral upload network error: {redact(str(exc), (access_key, api_key))}") from exc
    except json.JSONDecodeError as exc:
        raise CliError("Mintegral returned invalid JSON for upload") from exc
    if not isinstance(result, dict) or str(result.get("code")) != "200":
        raise CliError("Mintegral upload error: " + json.dumps(redact(result, (access_key, api_key)), ensure_ascii=False))
    return result


def data_list(result: dict[str, Any]) -> list[dict[str, Any]]:
    data = result.get("data")
    if isinstance(data, dict):
        items = data.get("list")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def find_offer(offer_id: Any, *, required: bool = True) -> dict[str, Any] | None:
    result = request_json(ACTIONS["offers"], {"offer_id": offer_id, "limit": 10})
    matches = [item for item in data_list(result) if str(item.get("offer_id")) == str(offer_id)]
    if len(matches) == 1:
        return matches[0]
    if required:
        raise CliError(f"Could not resolve exactly one offer for offer_id={offer_id}")
    return None


def find_campaign(campaign_id: Any, *, required: bool = True) -> dict[str, Any] | None:
    result = request_json(ACTIONS["campaigns"], {"campaign_id": campaign_id, "limit": 10})
    matches = [item for item in data_list(result) if str(item.get("campaign_id")) == str(campaign_id)]
    if len(matches) == 1:
        return matches[0]
    if required:
        raise CliError(f"Could not resolve exactly one campaign for campaign_id={campaign_id}")
    return None


def find_creative_set(offer_id: Any, creative_set_name: Any, *, required: bool = True) -> dict[str, Any] | None:
    result = request_json(ACTIONS["creative-sets"], {
        "offer_id": offer_id,
        "creative_set_name": creative_set_name,
        "limit": 10,
    })
    matches = [
        item for item in data_list(result)
        if str(item.get("offer_id")) == str(offer_id)
        and str(item.get("creative_set_name")) == str(creative_set_name)
    ]
    if len(matches) == 1:
        return matches[0]
    if required:
        raise CliError(
            "Could not resolve exactly one creative set for "
            f"offer_id={offer_id}, creative_set_name={creative_set_name}"
        )
    return None


def require_advertiser_maintained(current: dict[str, Any]) -> None:
    maintain_by = current.get("maintain_by")
    if maintain_by is not None and maintain_by != "ADV":
        raise CliError(f"Refusing mutation because maintain_by={maintain_by}, not ADV")


def preflight(action: Action, params: dict[str, Any]) -> dict[str, Any] | None:
    if action.preflight == "offer":
        offer_id = params.get("offer_id")
        if offer_id is None:
            return None
        current = find_offer(offer_id)
        assert current is not None
        require_advertiser_maintained(current)
        return current
    if action.preflight == "campaign":
        campaign_id = params.get("campaign_id")
        if campaign_id is None:
            return None
        current = find_campaign(campaign_id)
        assert current is not None
        require_advertiser_maintained(current)
        return current
    if action.preflight == "creative-set":
        offer = find_offer(params["offer_id"])
        assert offer is not None
        require_advertiser_maintained(offer)
        current = find_creative_set(params["offer_id"], params["creative_set_name"])
        assert current is not None
        return current
    return None


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def replacement_plan_hash(name: str, before: dict[str, Any], params: dict[str, Any]) -> str:
    return canonical_hash({"action": name, "before": before, "params": params})


def replacement_diff(name: str, before: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "offer-bid": ("bid_rate", "bid_rate_by_location", "bid_rate_by_mtgid"),
        "offer-budget": ("budget",),
        "publisher-target": ("option", "mtgid"),
    }.get(name, tuple(params))
    changes: dict[str, Any] = {}
    for field in fields:
        old_field = "bid_rate_for_mtgid" if field == "bid_rate_by_mtgid" and "bid_rate_for_mtgid" in before else field
        old = before.get(old_field, "[not returned by Mintegral]")
        new = params.get(field, "[omitted from replacement payload]")
        if old != new:
            changes[field] = {"before": old, "after": new}
    return changes


def values_equivalent(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict) and isinstance(actual, dict):
        return all(key in actual and values_equivalent(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(values_equivalent(left, right) for left, right in zip(expected, actual))
    if isinstance(expected, (int, float, str)) and isinstance(actual, (int, float, str)):
        try:
            return Decimal(str(expected)) == Decimal(str(actual))
        except InvalidOperation:
            return str(expected) == str(actual)
    return expected == actual


def compare_expected(params: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    ignored = {"campaign_id", "offer_id"}
    field_aliases = {
        "bid_rate_by_mtgid": "bid_rate_for_mtgid",
        "target_geo": "country_code",
    }
    mismatches: dict[str, Any] = {}
    for field, expected in params.items():
        if field in ignored:
            continue
        alias = field_aliases.get(field)
        actual_field = alias if alias in current else field
        if actual_field not in current or not values_equivalent(expected, current.get(actual_field)):
            mismatches[field] = {"expected": expected, "actual": current.get(actual_field, "[missing]")}
    return {"verified": not mismatches, "mismatches": mismatches, "current": current}


def response_id(response: dict[str, Any], field: str) -> Any:
    data = response.get("data")
    return data.get(field) if isinstance(data, dict) else None


def verify(name: str, action: Action, params: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    try:
        if name == "campaign-create":
            campaign_id = response_id(response, "campaign_id")
            if campaign_id is None:
                return {"verified": False, "warning": "Create response did not contain campaign_id"}
            current = find_campaign(campaign_id)
            assert current is not None
            return compare_expected(params, current)
        if name == "offer-create":
            offer_id = response_id(response, "offer_id")
            if offer_id is None:
                return {"verified": False, "warning": "Create response did not contain offer_id"}
            current = find_offer(offer_id)
            assert current is not None
            return compare_expected(params, current)
        if name == "campaign-update":
            current = find_campaign(params["campaign_id"])
            assert current is not None
            return compare_expected(params, current)
        if action.preflight == "offer":
            current = find_offer(params["offer_id"])
            assert current is not None
            return compare_expected(params, current)
        if name == "creative-set-update":
            current = find_creative_set(params["offer_id"], params["creative_set_name"])
            assert current is not None
            return compare_expected(params, current)
        if name == "creative-set-delete":
            current = find_creative_set(params["offer_id"], params["creative_set_name"], required=False)
            return {"verified": current is None, "current": current}
        return None
    except CliError as exc:
        return {"verified": False, "warning": str(exc)}


def write_output(result: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(redact(result), ensure_ascii=False, indent=2)
    if output:
        path = Path(output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except OSError as exc:
            raise CliError(f"Unable to open --output safely: {exc.strerror}") from exc
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            os.close(fd)
            raise CliError("--output must resolve to a regular file")
        if hasattr(os, "getuid") and file_stat.st_uid != os.getuid():
            os.close(fd)
            raise CliError("--output must be owned by the current user")
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
        print(str(path), file=sys.stderr)
    print(rendered)


def preview(
    name: str,
    action: Action,
    params: dict[str, Any],
    file_path: Path | None,
    before: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "preview": True,
        "executed": False,
        "action": name,
        "method": action.method,
        "host": "ss-storage-api.mintegral.com" if action.storage else "ss-api.mintegral.com",
        "path": action.path,
    }
    if file_path:
        result["file"] = str(file_path)
        result["size_bytes"] = file_path.stat().st_size if file_path.exists() else None
    else:
        result["params"] = redact(params)
    if action.preflight:
        result["execution_preflight"] = f"retrieve and verify current {action.preflight}; require maintain_by=ADV when returned"
    if action.full_replacement:
        result["warning"] = "This action can replace the complete existing configuration. Include every setting that must remain."
        if before is not None:
            result["before"] = before
            result["replacement_diff"] = replacement_diff(name, before, params)
            result["replacement_plan_hash"] = replacement_plan_hash(name, before, params)
    if action.destructive:
        result["warning"] = "This action deletes a creative set and requires --confirm-delete."
    return result


def command_check() -> int:
    result = {
        "python": sys.version.split()[0],
        "api_host": API_HOST,
        "storage_host": STORAGE_HOST,
        "MINTEGRAL_ACCESS_KEY": "configured" if os.environ.get("MINTEGRAL_ACCESS_KEY") else "missing",
        "MINTEGRAL_API_KEY": "configured" if os.environ.get("MINTEGRAL_API_KEY") else "missing",
    }
    print(json.dumps(result, indent=2))
    return 0 if result["MINTEGRAL_ACCESS_KEY"] == result["MINTEGRAL_API_KEY"] == "configured" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Check runtime and credential presence")
    sub.add_parser("list-actions", help="List fixed API actions")
    describe = sub.add_parser("describe", help="Describe one fixed action")
    describe.add_argument("--action", required=True, choices=sorted(ACTIONS))
    call = sub.add_parser("call", help="Preview or execute a fixed action")
    call.add_argument("--action", required=True, choices=sorted(ACTIONS))
    call.add_argument("--params-json")
    call.add_argument("--params-file")
    call.add_argument("--file")
    call.add_argument("--output")
    call.add_argument("--execute", action="store_true")
    call.add_argument("--acknowledge-full-replacement", action="store_true")
    call.add_argument("--replacement-plan-hash")
    call.add_argument("--confirm-delete", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return command_check()
    if args.command == "list-actions":
        write_output({name: action.description for name, action in ACTIONS.items()}, None)
        return 0
    if args.command == "describe":
        action = ACTIONS[args.action]
        write_output({
            "action": args.action,
            "method": action.method,
            "path": action.path,
            "description": action.description,
            "required": list(action.required),
            "mutation": action.mutation,
            "full_replacement": action.full_replacement,
            "destructive": action.destructive,
            "multipart": action.multipart,
        }, None)
        return 0

    name = args.action
    action = ACTIONS[name]
    params = load_params(args)
    validate_payload(name, action, params)
    file_path = Path(args.file).expanduser() if args.file else None
    if action.multipart and file_path is None:
        raise CliError(f"{name} requires --file")
    if not action.multipart and file_path is not None:
        raise CliError("--file is only valid for upload actions")

    if action.mutation and not args.execute:
        before = preflight(action, params) if action.full_replacement else None
        write_output(preview(name, action, params, file_path, before), args.output)
        return 0
    if action.full_replacement and not args.acknowledge_full_replacement:
        raise CliError("This action requires --acknowledge-full-replacement")
    if action.full_replacement and not args.replacement_plan_hash:
        raise CliError("This action requires --replacement-plan-hash from the immediately preceding preview")
    if action.destructive and not args.confirm_delete:
        raise CliError("This destructive action requires --confirm-delete")

    if action.multipart:
        result = upload(action, file_path)
        write_output({"executed": True, "action": name, "response": result}, args.output)
        return 0

    before = preflight(action, params) if action.mutation else None
    if action.full_replacement:
        assert before is not None
        actual_plan_hash = replacement_plan_hash(name, before, params)
        if actual_plan_hash != args.replacement_plan_hash:
            raise CliError(
                "Replacement plan hash mismatch: the current object or payload changed after preview. "
                "Run the preview again and review the new diff."
            )
    response = request_json(action, params)
    after = verify(name, action, params, response) if action.mutation else None
    result: dict[str, Any] = {"executed": action.mutation, "action": name, "response": response}
    if before is not None:
        result["before"] = before
    if after is not None:
        result["verification"] = after
    write_output(result, args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
