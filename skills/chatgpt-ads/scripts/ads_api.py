"""OpenAI Advertiser API transport and delivery reporting (standard library only)."""

import json
import os
import re
from datetime import date
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ORIGIN = "https://api.ads.openai.com/v1"
RESOURCES = {"campaign": "campaigns", "ad_group": "ad_groups", "ad": "ads"}
TRANSITION_STATUS = {"pause": "paused", "activate": "active", "archive": "archived"}


class AdsError(ValueError):
    pass


class AdsHTTPError(AdsError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise AdsError("Missing or invalid resource ID.")
    return value


def resource_path(kind, value):
    return f"/{RESOURCES[kind]}/{identifier(value)}"


def forbidden_hint(path):
    parts = path.strip("/").split("/")
    if parts[:2] in (["ad_account", "spend_limit_windows"], ["ad_account", "daily_spend_limit"]):
        return (
            " Account spending limits require permission to manage billing, including for reads. "
            "Ask the ad account admin to check Billing > Account limits and postpaid invoice eligibility. "
            "Existing daily limits can still be viewed and removed after a billing change."
        )
    if parts[0] == "lead_sync_subscriptions":
        return (
            " Verify access to the selected ad account and that Lead Sync is enabled. "
            "If it is not enabled, contact your OpenAI Ads representative or ads-support@openai.com "
            "with the ad account ID to request access."
        )
    return ""


class AdsAPI:
    def __init__(self):
        self.partner_token = os.getenv("OPENAI_ADS_OAUTH_TOKEN") or os.getenv("OPENAI_ADS_PARTNER_KEY")
        self.key = self.partner_token or os.environ.get("OPENAI_ADS_API_KEY", "").strip()
        self.selected_account = os.environ.get("OPENAI_ADS_ACCOUNT_ID") or None
        if self.selected_account:
            identifier(self.selected_account)
        self.opener = build_opener(NoRedirect())

    def partner_data_key(self):
        key = os.getenv("OPENAI_ADS_PARTNER_KEY") or os.getenv("OPENAI_ADS_API_KEY")
        if not key or not key.strip():
            raise AdsError("Partner Data requires an enabled OPENAI_ADS_PARTNER_KEY or OPENAI_ADS_API_KEY.")
        return key.strip()

    def request(
        self, method, path, body=None, *, query=(), key=None, service="ads", multipart=None, private=False
    ):
        events = service == "events"
        if events and path != "/events":
            raise AdsError("Unexpected Conversions API route.")
        token = os.environ.get("OPENAI_ADS_CAPI_KEY") if events else self.key
        if service == "partner_data":
            if not (path == "/partner_data/uploads" or path.startswith("/partner_data/uploads/")):
                raise AdsError("Unexpected Partner Data route.")
            token = self.partner_data_key()
        if not token:
            raise AdsError(
                "Set OPENAI_ADS_CAPI_KEY." if events else "Set OPENAI_ADS_API_KEY or a partner credential."
            )
        url = ("https://bzr.openai.com/v1" if events else ORIGIN) + path
        if query:
            url += "?" + urlencode(query)
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "User-Agent": "frevana-chatgpt-ads-skill/1.0",
        }
        if (
            self.partner_token
            and service == "ads"
            and path not in ("/me", "/ad_accounts", "/ad_account_creation_sessions")
        ):
            if not self.selected_account:
                raise AdsError("Select OPENAI_ADS_ACCOUNT_ID for this partner request.")
            headers["OpenAI-Ad-Account"] = self.selected_account
        data = None
        if multipart is not None:
            data, headers["Content-Type"] = multipart
        elif body is not None:
            data = json.dumps(body, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
            headers["Content-Type"] = "application/json"
        if key:
            headers["Idempotency-Key"] = key
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read()
        except HTTPError as exc:
            with exc:
                detail = (
                    "Private request rejected."
                    if private
                    else exc.read(4096).decode(errors="replace").replace(token, "[redacted]")
                )
            hint = forbidden_hint(path) if exc.code == 403 else ""
            raise AdsHTTPError(
                exc.code, f"{method} {path} returned HTTP {exc.code}: {detail}{hint}"
            ) from None
        except (URLError, OSError, HTTPException) as exc:
            raise AdsError(f"{method} {path}: transport failed ({type(exc).__name__}).") from None
        if not raw and method in ("POST", "PATCH", "DELETE"):
            return {}  # State transitions are verified by GET.
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AdsError(f"{method} {path} returned invalid JSON.") from None
        if not isinstance(result, dict) or (
            result.get("error") and not any(k in result for k in ("data", "status", "complete"))
        ):
            raise AdsError(f"{method} {path} returned an unexpected response.")
        return result


def account_info(api):
    result = api.request("GET", "/ad_account")
    identifier(result.get("id"))
    if getattr(api, "selected_account", None) and result["id"] != api.selected_account:
        raise AdsError("The API returned an account different from OPENAI_ADS_ACCOUNT_ID.")
    if not all(isinstance(result.get(k), str) and result[k] for k in ("currency_code", "timezone")):
        raise AdsError("Account response is missing currency or timezone.")
    fields = ("id", "name", "account_name", "brand_name", "currency_code", "timezone", "status", "review")
    return {k: result[k] for k in fields if k in result}


def native_matches(wanted, actual):
    if isinstance(wanted, dict):
        return isinstance(actual, dict) and all(native_matches(v, actual.get(k)) for k, v in wanted.items())
    return wanted == actual


def read_resource(api, kind, resource_id):
    result = api.request("GET", resource_path(kind, resource_id))
    if result.get("id") != resource_id or not isinstance(result.get("status"), str):
        raise AdsError(f"Invalid {kind} readback for {resource_id}.")
    return result


def report(api, args):
    since, until = date.fromisoformat(args.since), date.fromisoformat(args.until)
    if since > until:
        raise AdsError("--since must be on or before --until.")
    if (args.scope == "ad_account") != (args.id is None):
        raise AdsError("Supply --id for a campaign, ad_group or ad; omit it for ad_account.")
    levels = ["ad_account", *RESOURCES]
    level = args.level or ("campaign" if args.scope == "ad_account" else args.scope)
    if levels.index(level) < levels.index(args.scope):
        raise AdsError("--level must be the selected scope or a child level.")
    path = "/ad_account" if args.scope == "ad_account" else resource_path(args.scope, args.id)
    account = account_info(api)
    period = {
        "type": "date_range",
        "since": since.isoformat(),
        "until": until.isoformat(),
        "timezone": account["timezone"],
    }
    metrics = ["impressions", "clicks", "spend", "ctr", "cpc", "cpm"]
    fields = [f"{level}.{field}" for field in ["id", "name", *metrics]]
    if args.granularity != "none":
        fields.append("metadata.readable_time")
    query = [
        ("aggregation_level", level),
        ("time_granularity", args.granularity),
        ("time_ranges[]", json.dumps(period)),
        ("limit", "500"),
    ]
    query.extend(("fields[]", field) for field in fields)
    if getattr(args, "options", None):
        from ads_operations import CATALOG, checked_fields, object_file, query_pairs

        options = object_file(args.options)
        names = (
            "fields",
            "filters",
            "sort",
            "segments",
            "includes",
            "override_segment_group_order",
            "attribution_window_days",
            "view_through_attribution_window_days",
            "attribution_time_basis",
        )
        checked_fields(options, names, [])
        if "fields" in options:
            query = [(k, v) for k, v in query if k != "fields[]"]
        query.extend(query_pairs(CATALOG["get-ad-account-insights"], options))
    rows, cursors = [], set()
    cursor = None
    while True:
        page_query = query + ([("after", cursor)] if cursor else [])
        page = api.request("GET", path + "/insights", query=page_query)
        if not isinstance(page.get("data"), list) or type(page.get("has_more")) is not bool:
            raise AdsError("Invalid Insights page; report incomplete.")
        rows.extend(page["data"])
        if not page["has_more"]:
            break
        cursor = page.get("last_id")
        if not isinstance(cursor, str) or not cursor or cursor in cursors:
            raise AdsError("Missing or repeated Insights cursor; report incomplete.")
        cursors.add(cursor)
    return {
        "account": account,
        "scope": args.scope,
        "resource_id": args.id,
        "level": level,
        "time_range": period,
        "granularity": args.granularity,
        **({"options": options} if getattr(args, "options", None) else {}),
        "data": rows,
    }
