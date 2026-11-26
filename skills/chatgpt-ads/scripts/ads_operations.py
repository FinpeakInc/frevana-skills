"""Named operations from the Ads OpenAPI contract and documented guide-only endpoints."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlsplit

from ads_api import AdsError, identifier
from ads_bulk import bulk_results_cursor, validate_bulk

CATALOG = json.loads((Path(__file__).resolve().parents[1] / "references/operations.json").read_text())
FILES = {"upload-image", "upload-blob", "upload-feed-snapshot"}


def is_read(op):
    return op["method"] == "GET" or op.get("read", False)


def describe(name):
    op = CATALOG[name]
    return {
        "action": name,
        "access": "read" if is_read(op) else "plan",
        **op,
        "path_parameters": re.findall(r"{(\w+)}", op["path"]),
    }


def object_file(path):
    if path is None:
        return {}
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise AdsError("Expected a JSON object.")
    return obj


def checked_fields(obj, allowed, required):
    extra = sorted(set(obj) - set(allowed))
    missing = sorted(set(required) - set(obj))
    if extra or missing:
        raise AdsError(f"Unknown fields {extra}; missing fields {missing}.")


def operation_path(op, params):
    return op["path"].format(**{k: quote(v, safe="") for k, v in params.items()})


def webhook_origin(url):
    if (
        not isinstance(url, str)
        or len(url) > 2048
        or not url.startswith("https://")
        or any(c.isspace() for c in url)
    ):
        raise AdsError("destination_url must be an HTTPS URL of at most 2048 characters.")
    parsed = urlsplit(url)
    if not parsed.hostname:
        raise AdsError("destination_url must include the HTTPS host.")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"https://{host}" + (f":{parsed.port}" if parsed.port is not None else "")


def validate_partner_manifest(body):
    if body["data_type"] != "identity_graph":
        raise AdsError("Partner snapshot data_type must be identity_graph.")
    day = body["snapshot_date"]
    if not isinstance(day, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
        raise AdsError("snapshot_date must be YYYY-MM-DD.")
    date.fromisoformat(day)
    filename = body["file_name"]
    if (
        not isinstance(filename, str)
        or len(filename) > 200
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.parquet", filename)
    ):
        raise AdsError("file_name must be a .parquet basename of at most 200 characters.")
    size = body["file_size_bytes"]
    if type(size) is not int or not 1 <= size <= 107374182400:
        raise AdsError("file_size_bytes must be an integer from 1 to 107374182400.")
    if not isinstance(body["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", body["sha256"]):
        raise AdsError("sha256 must contain 64 lowercase hexadecimal characters.")


def query_pairs(op, query):
    shapes = op.get("query", {})
    checked_fields(query, shapes, op.get("required_query", []))
    pairs = []
    for name, v in query.items():
        shape = shapes[name]
        if shape == "array":
            if not isinstance(v, list):
                raise AdsError(f"{name} requires a JSON array.")
            for item in v:
                pairs.append(
                    (name + "[]", item if isinstance(item, str) else json.dumps(item, separators=(",", ":")))
                )
        else:
            if (
                shape == "integer"
                and type(v) is not int
                or shape == "boolean"
                and type(v) is not bool
                or shape == "string"
                and not isinstance(v, str)
                or isinstance(v, (dict, list))
                or v is None
            ):
                raise AdsError(f"Invalid query parameter {name}.")
            pairs.append((name, str(v).lower() if isinstance(v, bool) else str(v)))
    if "before" in query and "after" in query:
        raise AdsError("Choose one pagination direction.")
    return pairs


def file_ref(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise AdsError("Expected a regular file.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest.hexdigest()}


def read_ref(ref):
    data = Path(ref["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise AdsError("File contents changed since preview. Prepare a new proposal.")
    return data


def request_parts(args):
    name = args.action
    op = describe(name)
    params = {}
    for part in args.param:
        k, sep, v = part.partition("=")
        if not sep or k in params:
            raise AdsError("Use one --param name=id per path parameter.")
        if k == "subscription_id" and name in ("get-lead-sync-subscription", "delete-lead-sync-subscription"):
            if not 1 <= len(v) <= 256 or v in (".", "..") or any(ord(c) < 32 for c in v):
                raise AdsError("Invalid subscription_id.")
            params[k] = v
        else:
            params[k] = identifier(v)
    checked_fields(params, op["path_parameters"], op["path_parameters"])
    query = object_file(args.query)
    query_pairs(op, query)
    if name == "list-lead-sync-subscriptions" and not 1 <= len(query["ad_account_id"]) <= 256:
        raise AdsError("Supply the authorized ad_account_id.")
    if name == "get-partner-data-upload" and not re.fullmatch(r"pdu_[0-9a-f]{32}", params["upload_id"]):
        raise AdsError("Expected a Partner Data upload_id (pdu_ followed by 32 lowercase hex digits).")
    body = object_file(args.body)
    file = getattr(args, "file", None)
    if "file" in body or (file and name not in FILES):
        raise AdsError("Supply binary input only with --file on an upload operation.")
    required = [k for k in op.get("required", []) if k != "file"]
    checked_fields(body, op.get("fields", []), required)
    if name == "create-partner-data-upload":
        validate_partner_manifest(body)
    if name == "create-lead-sync-subscription":
        webhook_origin(body["destination_url"])
        if "signing_secret" in body and (
            not isinstance(body["signing_secret"], str)
            or not re.fullmatch(r"whsec_[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=", body["signing_secret"])
        ):
            raise AdsError("Invalid webhook signing_secret format.")
    if name in ("upload-blob", "upload-feed-snapshot") and not file:
        raise AdsError("This action requires --file.")
    if name == "upload-image" and bool(file) == bool(body.get("image_url")):
        raise AdsError("Choose one --file or image_url.")
    if name == "upload-blob" and body.get("purpose", "custom_audience") != "custom_audience":
        raise AdsError("Use purpose custom_audience for an audience upload.")
    if name == "upload-blob":
        body.setdefault("purpose", "custom_audience")
    if name in ("add-custom-audience-members", "remove-custom-audience-members") and (
        bool(body.get("file_id")) == bool(body.get("identifiers"))
    ):
        raise AdsError("Supply exactly one file_id or identifiers array.")
    if name == "upload-feed-snapshot" and (
        not re.fullmatch(r"[\w.-]+", body["remote_name"], flags=re.ASCII)
        or body["remote_name"].startswith((".", "-"))
    ):
        raise AdsError("Use a plain file name in the SFTP root.")
    if name == "create-bulk-job":
        validate_bulk(body)
    if name == "send-conversion-events":
        identifier(query["pid"])
        validate_events(body)
    if name == "post-conversion-insights":
        # This POST encodes its single full-day range as a JSON string in the array.
        ranges = body["time_ranges"]
        if not isinstance(ranges, list) or len(ranges) != 1:
            raise AdsError("Supply one conversion reporting time_range.")
        if isinstance(ranges[0], dict):
            body["time_ranges"] = [json.dumps(ranges[0], separators=(",", ":"))]
        elif not isinstance(ranges[0], str):
            raise AdsError("Invalid conversion reporting time_range.")
    # Read once when sealing private JSON so the digest binds exactly what was validated.
    private_ref = None
    if op.get("private_body") and args.body:
        private_ref = file_ref(args.body)
        if json.loads(read_ref(private_ref)) != body:
            raise AdsError("Body changed while preparing the proposal.")
    return {
        "action": name,
        "params": params,
        "query": query,
        "body": None if private_ref else body,
        "private_body": private_ref,
        "file": file_ref(file) if file else None,
    }, body


def validate_events(body):
    events = body.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= 1000:
        raise AdsError("Supply 1–1000 conversion events.")
    identities = set()
    for event in events:
        if not isinstance(event, dict):
            raise AdsError("Expected a conversion event object.")
        # Stable IDs let the browser and server identify the same real conversion.
        if not all(isinstance(event.get(k), str) and event[k] for k in ("type", "id")):
            raise AdsError("Provide the real event type and a stable event id for deduplication.")
        identity = (event["type"], event.get("custom_event_name"), event["id"])
        if identity in identities:
            raise AdsError("Duplicate conversion event in this batch.")
        identities.add(identity)
        if type(event.get("timestamp_ms")) is not int or not isinstance(event.get("data"), dict):
            raise AdsError("Conversion event requires timestamp_ms and data.")
        if event["type"] == "custom" and not event.get("custom_event_name"):
            raise AdsError("A custom event requires custom_event_name.")
        if event.get("action_source") == "web" and not event.get("source_url"):
            raise AdsError("Web events require source_url.")


def read_pages(api, spec, body, all_pages):
    op = CATALOG[spec["action"]]
    if not is_read(op):
        raise AdsError("A mutation requires plan and confirmed execute.")
    path = operation_path(op, spec["params"])
    q = dict(spec["query"])
    if spec["action"] == "list-lead-sync-subscriptions" and getattr(api, "selected_account", None) not in (
        None,
        q["ad_account_id"],
    ):
        raise AdsError("Requested ad_account_id differs from OPENAI_ADS_ACCOUNT_ID.")
    body = dict(body)
    if all_pages and "before" in q:
        raise AdsError("--all-pages follows forward cursors.")
    if all_pages and spec["action"] == "list-product-feed-uploads":
        q["paginate"] = True
    seen = set()
    while True:
        transport = {"service": op["service"]} if "service" in op else {}
        result = api.request(
            op["method"], path, body if "fields" in op else None, query=query_pairs(op, q), **transport
        )
        yield result
        if not all_pages:
            return
        last_id = (
            bulk_results_cursor(result) if spec["action"] == "list-bulk-results" else result.get("last_id")
        )
        if spec["action"] == "get-partner-eligibility-results":
            cursor = result.get("next_offset")
            if cursor is None:
                break
            field = "offset"
        elif result.get("has_more") is True:
            field, cursor = "after", last_id
            if spec["action"] == "list-custom-audience-operations":
                field, cursor = "cursor", result.get("next_cursor")
        else:
            if result.get("truncated"):
                raise AdsError("The API returned a truncated page.")
            if (
                op["method"] == "POST"
                and isinstance(result.get("matched_count"), int)
                and result.get("has_more") is None
                and len(result.get("data", [])) < result["matched_count"]
            ):
                raise AdsError("The API returned a partial result without a pagination cursor.")
            break
        if cursor in (None, "") or cursor in seen:
            raise AdsError("Invalid pagination cursor; read is incomplete.")
        seen.add(cursor)
        (body if op["method"] == "POST" else q)[field] = cursor


def call_read(api, spec, body, all_pages):
    results = read_pages(api, spec, body, all_pages)
    if not all_pages:
        return next(results)
    # Preserve per-page review maps, native row keys, and partial-failure metadata.
    pages = list(results)
    return {"page_count": len(pages), "pages": pages}
