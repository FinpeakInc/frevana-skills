#!/usr/bin/env python3
"""Frevana Pins CLI; Python standard library only."""

import argparse
import copy
import http.client
import json
import os
import re
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


MIME_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif", ".webm": "video/webm",
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
}
MAX_BYTES = 100 * 1024 * 1024


class PinsError(Exception):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_upload(file):
    content_type = MIME_TYPES.get(file.suffix.lower())
    if not content_type:
        raise PinsError("Unsupported file extension")
    if not file.is_file():
        raise PinsError("Upload path must be an existing regular file")
    if not 0 < file.stat().st_size <= MAX_BYTES:
        raise PinsError("File must contain 1 to 104857600 bytes")
    return content_type


class Client:
    def __init__(self, base_url, token, timeout=60):
        parsed = urllib.parse.urlsplit(base_url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise PinsError("FREVANA_API_BASE_URL must be an HTTP(S) root URL without credentials, query or fragment")
        if not token or any(c.isspace() for c in token):
            raise PinsError("FREVANA_TOKEN must contain a valid bearer token")
        self.base_url = base_url.rstrip("/") + "/user-pins"
        self.token = token
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path="", payload=None, raw=None, content_type=None, binary=False):
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/json",
                   "User-Agent": "frevana-pins-skill/1"}
        if payload is not None:
            raw = json.dumps(payload).encode()
            content_type = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(self.base_url + path, data=raw, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                body = response.read()
            return body if binary else json.loads(body)
        except urllib.error.HTTPError as error:
            error.close()
            hint = "Check FREVANA_TOKEN or --token" if error.code == 401 else "API request failed"
            raise PinsError(hint, http_status=error.code, request_method=method) from None
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError):
            message = "API connection failed"
            details = {"request_method": method}
            if method != "GET":
                message += "; write outcome may be unknown, inspect the library before retrying"
                details["save_status"] = "outcome_unknown"
            raise PinsError(message, **details) from None
        except (ValueError, UnicodeError):
            raise PinsError("API returned invalid JSON; inspect the library before retrying writes") from None

    def store(self):
        result = self.request("GET")
        if (not isinstance(result, dict) or result.get("version") != 1
                or not isinstance(result.get("pins"), list)
                or not isinstance(result.get("collections"), list)):
            raise PinsError("Unexpected library response")
        for field in ("pins", "collections"):
            items = result[field]
            if any(not isinstance(item, dict) or not isinstance(item.get("id"), str)
                   or not item["id"] for item in items):
                raise PinsError("Unexpected library records", record_type=field)
            if len({item["id"] for item in items}) != len(items):
                raise PinsError("Duplicate record IDs; repair the library before editing", record_type=field)
        if any(not isinstance(c.get("pinIds"), list) for c in result["collections"]):
            raise PinsError("Unexpected collection membership")
        return result

    def upload(self, file):
        content_type = validate_upload(file)
        data = file.read_bytes()
        if not 0 < len(data) <= MAX_BYTES:
            raise PinsError("File size changed; upload refused")
        boundary = "pins-" + uuid.uuid4().hex
        # Use a generated ASCII filename to avoid multipart header injection.
        header = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                  f'filename="upload{file.suffix.lower()}"\r\nContent-Type: {content_type}\r\n\r\n').encode()
        body = header + data + f"\r\n--{boundary}--\r\n".encode()
        result = self.request("POST", "/assets", raw=body,
                              content_type="multipart/form-data; boundary=" + boundary)
        if not isinstance(result, dict) or not isinstance(result.get("path"), str) or not result["path"]:
            raise PinsError("Unexpected upload response; inspect uploaded assets before retrying")
        return result, content_type


def now():
    return int(time.time() * 1000)


def find(items, identifier, label):
    found = next((item for item in items if item["id"] == identifier), None)
    if found is None:
        raise PinsError(f"{label} not found", record_id=identifier)
    return found


def fingerprint(snapshot):
    result = copy.deepcopy(snapshot)
    # A missing index is presented with a fresh timestamp on every GET.
    # Empty libraries have no content change to protect via that timestamp.
    if not result["pins"] and not result["collections"]:
        result.pop("updatedAt", None)
    # Signed GET URLs may be reissued on every read.
    for pin in result["pins"]:
        for field in ("mediaUrl", "posterUrl"):
            value = pin.get(field)
            if value and "X-Amz-Signature=" in value:
                pin[field] = value.split("?", 1)[0]
    return result


def media_identity(value):
    if not value:
        return value
    parsed = urllib.parse.urlsplit(value)
    path = urllib.parse.unquote(parsed.path).lstrip("/") if parsed.scheme else value
    if ".." in path:
        return value
    if parsed.scheme:
        # Mirror the API's S3 and legacy Supabase Pins namespaces. Do not
        # collapse arbitrary external URLs merely because they contain assets/.
        legacy = re.search(r"(?:^|/)object/(?:sign|authenticated|public)/pins/([^/]+/assets/.+)$", path)
        if legacy:
            path = legacy.group(1)
        elif not re.match(r"^pins(?:-dev)?/[^/]+/assets/.+$", path):
            return value
    path = re.sub(r"^pins(?:-dev)?/", "", path)
    if re.match(r"^[^/]+/assets/.+$", path):
        return path.split("/", 1)[1]
    return value


def save(client, original, desired, fields):
    if all(desired[field] == original[field] for field in fields):
        return original
    if fingerprint(client.store()) != fingerprint(original):
        raise PinsError("Library changed before save; fetch the latest library and repeat the intended edit")
    client.request("PUT", payload={field: desired[field] for field in fields})
    try:
        actual = client.store()
    except PinsError as error:
        raise PinsError("Write succeeded but verification could not complete; inspect the library before retrying",
                        save_status="submitted_unverified", **error.details) from None
    for field in fields:
        expected_items = desired[field]
        actual_items = actual[field]
        if field == "pins":
            # Compare stable media paths as well as metadata after URL signing.
            def comparable(items):
                return [{k: media_identity(v) if k in ("mediaUrl", "posterUrl") else v
                         for k, v in item.items()} for item in items]
            matches = comparable(expected_items) == comparable(actual_items)
        else:
            matches = sorted(expected_items, key=lambda item: item["id"]) == sorted(actual_items, key=lambda item: item["id"])
        if not matches:
            raise PinsError("Save verification failed; inspect the current library before retrying",
                            save_status="submitted_unverified")
    return actual


def move(snapshot, pin_ids, collection_id=None):
    for pin_id in pin_ids:
        find(snapshot["pins"], pin_id, "Pin")
    target = find(snapshot["collections"], collection_id, "Collection") if collection_id else None
    ids = set(pin_ids)
    for collection in snapshot["collections"]:
        old = collection["pinIds"][:]
        collection["pinIds"] = [pin_id for pin_id in old if pin_id not in ids]
        if collection is target:
            collection["pinIds"].extend(dict.fromkeys(pin_ids))
        if old != collection["pinIds"]:
            collection["updatedAt"] = now()


def add_pin(client, args, media_url, content_type=None):
    original = client.store()
    if len(original["pins"]) >= 100:
        raise PinsError("Pin limit (100) reached")
    desired = copy.deepcopy(original)
    identifier = str(uuid.uuid4())
    pin = {"id": identifier, "kind": args.kind, "sourceUrl": args.source_url or "",
           "mediaUrl": media_url, "savedAt": now()}
    for field, value in (("title", args.title), ("sourcePageUrl", args.source_page_url),
                         ("posterUrl", getattr(args, "poster_url", None)), ("contentType", content_type)):
        if value:
            pin[field] = value.strip() if field == "title" else value
    desired["pins"].insert(0, pin)
    fields = ["pins"]
    if args.collection_id:
        move(desired, [identifier], args.collection_id)
        fields.append("collections")
    try:
        saved = save(client, original, desired, fields)
    except PinsError as error:
        error.details["pin_id"] = identifier
        raise
    return {"pin_id": identifier, "data": find(saved["pins"], identifier, "Pin")}


def execute(client, args):
    if args.command == "present":
        return {"data": client.request("POST", "/present", payload={"urls": args.refs})}
    if args.command == "upload-url":
        payload = {"fileName": args.file_name}
        if args.content_type:
            payload["contentType"] = args.content_type
        result = client.request("POST", "/assets/upload-url", payload=payload)
        if (not isinstance(result, dict) or not result.get("path")
                or not isinstance(result.get("signedUrl"), str)):
            raise PinsError("Unexpected upload URL response")
        return {"data": result}
    if args.command == "upload":
        file = Path(args.file).expanduser()
        validate_upload(file)
        if not args.asset_only:
            current = client.store()
            if len(current["pins"]) >= 100:
                raise PinsError("Pin limit (100) reached")
            if args.collection_id:
                find(current["collections"], args.collection_id, "Collection")
        asset, content_type = client.upload(file)
        if args.asset_only:
            return {"asset_path": asset["path"], "url": asset.get("url")}
        args.kind = "video" if content_type.startswith("video/") else "image"
        args.title = args.title or Path(args.file).name
        try:
            result = add_pin(client, args, asset["path"], content_type)
        except PinsError as error:
            error.details["asset_path"] = asset["path"]
            raise
        return dict(result, asset_path=asset["path"])
    if args.command == "add":
        return add_pin(client, args, args.media_url, args.content_type)

    original = client.store()
    if args.command == "list":
        pins = original["pins"]
        if args.collection_id:
            ids = find(original["collections"], args.collection_id, "Collection")["pinIds"]
            pins = [pin for pin in pins if pin["id"] in ids]
        if args.kind:
            pins = [pin for pin in pins if pin["kind"] == args.kind]
        return {"data": dict(original, pins=pins)}
    if args.command == "download":
        pin = find(original["pins"], args.pin_id, "Pin")
        # Require a user-owned ref: this endpoint does not fetch arbitrary external URLs.
        query = urllib.parse.urlencode({"src": pin["mediaUrl"], "proxy": "1"})
        output = Path(args.output).expanduser()
        if output.exists():
            raise PinsError("Output already exists")
        data = client.request("GET", "/assets?" + query, binary=True)
        with output.open("xb") as handle:
            handle.write(data)
        return {"output_path": str(output.resolve()), "bytes_written": len(data)}

    desired = copy.deepcopy(original)
    if args.command == "remove":
        find(desired["pins"], args.pin_id, "Pin")
        move(desired, [args.pin_id])
        desired["pins"] = [pin for pin in desired["pins"] if pin["id"] != args.pin_id]
        return {"data": save(client, original, desired, ["pins", "collections"])}
    action = args.collection_command
    if action == "list":
        return {"data": original["collections"]}
    if action == "create":
        if len(desired["collections"]) >= 40:
            raise PinsError("Collection limit (40) reached")
        identifier = "collection_" + str(uuid.uuid4())
        desired["collections"].append({"id": identifier, "title": args.title,
                                       "createdAt": now(), "updatedAt": now(), "pinIds": []})
        move(desired, args.pin_ids, identifier)
    elif action == "rename":
        collection = find(desired["collections"], args.collection_id, "Collection")
        collection.update(title=args.title, updatedAt=now())
    elif action == "delete":
        find(desired["collections"], args.collection_id, "Collection")
        desired["collections"] = [c for c in desired["collections"] if c["id"] != args.collection_id]
    elif action in ("move", "ungroup"):
        move(desired, args.pin_ids, getattr(args, "collection_id", None))
    result = {"data": save(client, original, desired, ["collections"])}
    if action == "create":
        result["collection_id"] = identifier
    return result


def nonempty(value):
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value.strip()


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def add_common_options(root):
    # Suppressed defaults let options work before or after any subcommand.
    root.add_argument("--token", default=argparse.SUPPRESS, help="one-time JWT override; prefer FREVANA_TOKEN")
    root.add_argument("--api-base-url", default=argparse.SUPPRESS, help="API root override")
    root.add_argument("--timeout", type=positive_int, default=argparse.SUPPRESS, help="per-request timeout in seconds (default 60)")
    root.add_argument("--output-json", default=argparse.SUPPRESS, help="also save result JSON; never overwrite an existing file")
    for action in root._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                add_common_options(sub)


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="List current Pins")
    listing.add_argument("--kind", choices=["image", "video"])
    listing.add_argument("--collection-id")
    for command in ("upload", "add"):
        sub = commands.add_parser(command)
        sub.add_argument("--title", type=nonempty)
        sub.add_argument("--source-url")
        sub.add_argument("--source-page-url")
        sub.add_argument("--collection-id")
        if command == "upload":
            sub.add_argument("file")
            sub.add_argument("--asset-only", action="store_true")
        else:
            sub.add_argument("--kind", choices=["image", "video"], required=True)
            sub.add_argument("--media-url", type=nonempty, required=True)
            sub.add_argument("--poster-url")
            sub.add_argument("--content-type", choices=sorted(set(MIME_TYPES.values())))
    commands.add_parser("remove").add_argument("pin_id")
    commands.add_parser("present").add_argument("refs", nargs="+")
    upload_url = commands.add_parser("upload-url")
    upload_url.add_argument("file_name", type=nonempty)
    upload_url.add_argument("--content-type", choices=sorted(set(MIME_TYPES.values())))
    download = commands.add_parser("download")
    download.add_argument("pin_id")
    download.add_argument("--output", required=True)
    collection = commands.add_parser("collection").add_subparsers(dest="collection_command", required=True)
    collection.add_parser("list")
    create = collection.add_parser("create")
    create.add_argument("title", type=nonempty)
    create.add_argument("--pin-ids", nargs="+", default=[])
    rename = collection.add_parser("rename")
    rename.add_argument("collection_id")
    rename.add_argument("title", type=nonempty)
    collection.add_parser("delete").add_argument("collection_id")
    move_cmd = collection.add_parser("move")
    move_cmd.add_argument("collection_id")
    move_cmd.add_argument("--pin-ids", nargs="+", required=True)
    collection.add_parser("ungroup").add_argument("--pin-ids", nargs="+", required=True)
    add_common_options(root)
    root.set_defaults(token=None, api_base_url=None, timeout=60, output_json=None)
    return root


def main():
    args = parser().parse_args()
    output_handle = None
    output_path = None
    output_complete = False
    try:
        base_url = args.api_base_url or os.environ.get("FREVANA_API_BASE_URL", "https://api.frevana.com")
        token = args.token if args.token is not None else os.environ.get("FREVANA_TOKEN", "")
        if not token:
            raise PinsError("FREVANA_TOKEN is not set; supply it through the environment or --token")
        client = Client(base_url, token, args.timeout)
        if args.command == "upload" and args.asset_only and args.collection_id:
            raise PinsError("--asset-only cannot be combined with --collection-id")
        if args.output_json:
            output_path = Path(args.output_json).expanduser()
            # Reserve the file before any request, so output errors cannot trigger a write.
            output_handle = output_path.open("x", encoding="utf-8")
            os.chmod(output_path, 0o600)
        result = execute(client, args)
        rendered = json.dumps(dict(ok=True, action=args.command, **result), ensure_ascii=False)
        if output_handle:
            try:
                output_handle.write(rendered + "\n")
                output_handle.flush()
                output_handle.close()
            except OSError:
                # The API operation is already complete. Keep its full result
                # on stdout and stable recovery identifiers in the JSON error.
                print(rendered)
                recovery = {key: result[key] for key in (
                    "pin_id", "asset_path", "collection_id", "output_path", "bytes_written",
                ) if key in result}
                raise PinsError("Operation completed but result JSON could not be saved; do not repeat the operation",
                                operation_status="completed", output_json_status="failed", **recovery) from None
            output_complete = True
        print(rendered)
        return 0
    except PinsError as error:
        print(json.dumps(dict(ok=False, error=str(error), **error.details), ensure_ascii=False), file=sys.stderr)
        return 1
    except OSError:
        print(json.dumps({"ok": False, "error": "Local file operation failed"}), file=sys.stderr)
        return 1
    finally:
        if output_handle:
            try:
                output_handle.close()
            except OSError:
                # A buffered close failure must not mask the structured error.
                pass
            if not output_complete:
                try:
                    output_path.unlink()
                except OSError:
                    pass


if __name__ == "__main__":
    sys.exit(main())
