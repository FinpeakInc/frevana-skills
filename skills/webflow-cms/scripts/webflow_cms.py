#!/usr/bin/env python3
"""Publish Webflow CMS items through Data API v2 live endpoints."""
import json
import re
import sys
from urllib.parse import quote, urlencode, urlsplit

from cms_common import Config, Failure, cli_main, http, parser_for, read_json, require, text_field

FIELDS = ("site_id", "site_url", "api_token", "collection_id", "name_field_slug", "slug_field_slug",
          "content_field_slug", "summary_field_slug")
DEFAULTS = {"name_field_slug": "name", "slug_field_slug": "slug"}
SETUP_GUIDE = "https://frevana.gitbook.io/frevana-docs/cms-integrations/webflow-integration"


def identifier(value):
    require(bool(re.fullmatch(r"[a-fA-F0-9]{24,32}", value or "")), "Expected a Webflow object ID")
    return value


def site_url(value):
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment and parsed.path in ("", "/"),
            "site_url must be an HTTPS site origin")
    return value


def validate_config(values):
    identifier(values["site_id"])
    values["site_url"] = site_url(values["site_url"])
    if values["collection_id"]:
        identifier(values["collection_id"])


class Webflow:
    def __init__(self, config):
        config.need("site_id", "site_url", "api_token")
        self.values = config.values
        identifier(self.values["site_id"])
        site_url(self.values["site_url"])

    def request(self, method, path, data=None):
        return http(method, "https://api.webflow.com/v2" + path,
                    {"Authorization": "Bearer " + self.values["api_token"],
                     "Accept": "application/json", "Content-Type": "application/json"}, data)

    def collections(self):
        return self.request("GET", f"/sites/{self.values['site_id']}/collections")

    def collection(self):
        collection_id = identifier(self.values["collection_id"])
        response = self.collections()
        require(isinstance(response.get("collections"), list), "Missing collections list")
        require(any(c.get("id") == collection_id for c in response["collections"]),
                "Selected collection does not belong to configured site")
        details = self.request("GET", f"/collections/{collection_id}")
        require(details.get("id") == collection_id and isinstance(details.get("fields"), list),
                "Invalid collection details response")
        return details

    def item(self, value, live=False):
        item_id = identifier(value)
        result = self.request("GET", f"/collections/{identifier(self.values['collection_id'])}/items/{item_id}"
                              + ("/live" if live else ""))
        require(result.get("id") == item_id and isinstance(result.get("fieldData"), dict),
                "Item response has missing or mismatched identity/fieldData")
        return result


def item_payload(args, config):
    config.need("site_id", "site_url", "collection_id", "content_field_slug")
    identifier(config.values["site_id"])
    identifier(config.values["collection_id"])
    require(args.data_file, "--data-file is required")
    data = read_json(args.data_file)
    require(not set(data) - {"title", "slug", "bodyHtml", "summary", "fieldData"}, "Unknown content fields")
    for key in ("title", "slug", "bodyHtml"):
        text_field(data, key, required=True)
    text_field(data, "summary")
    require(not re.search(r"[/?#\s]", data["slug"]), "slug must be one nonempty URL segment without whitespace")
    mapping = {"title": config.values["name_field_slug"], "slug": config.values["slug_field_slug"],
               "bodyHtml": config.values["content_field_slug"]}
    if config.values["summary_field_slug"]:
        mapping["summary"] = config.values["summary_field_slug"]
    require(all(re.fullmatch(r"[a-z0-9][a-z0-9-]*", v) for v in mapping.values()), "Invalid field slug")
    require(len(set(mapping.values())) == len(mapping), "Field mappings must use distinct slugs")
    require("summary" not in data or "summary" in mapping, "summary requires summary_field_slug")
    extras = data.get("fieldData", {})
    require(isinstance(extras, dict), "fieldData must be an object of additional collection fields")
    require(not set(extras).intersection(mapping.values()), "fieldData conflicts with mapped content fields")
    fields = {**extras, **{slug: data[key] for key, slug in mapping.items() if key in data}}
    return {"isArchived": False, "isDraft": False, "fieldData": fields}


def validate_fields(config, collection, payload, current=None):
    schema = {f["slug"]: f for f in collection["fields"] if isinstance(f, dict) and "slug" in f}
    fields = payload["fieldData"]
    require(not set(fields) - set(schema), "Unknown collection fields: " + ", ".join(sorted(set(fields) - set(schema))))
    content = config.values["content_field_slug"]
    require(schema.get(content, {}).get("type") == "RichText", "Body mapping must target a RichText field")
    for key in ("name_field_slug", "slug_field_slug", "summary_field_slug"):
        slug = config.values[key]
        if slug:
            require(schema.get(slug, {}).get("type") == "PlainText", key + " must target a PlainText field")
    merged = {**(current or {}).get("fieldData", {}), **fields}
    for slug, field in schema.items():
        if slug in fields:
            require(field.get("isEditable") is not False, f"Field {slug} is not editable")
        if field.get("isRequired"):
            require(slug in merged and merged[slug] is not None and merged[slug] != "" and merged[slug] != [],
                    f"Required collection field is missing: {slug}")
    # Provider remains authoritative for field-specific validation and references.


def run(args, config):
    if args.action == "configure":
        return config.configure(("site_id", "site_url", "api_token"), validate_config)
    if args.action in ("create", "update"):
        payload = item_payload(args, config)
        if args.action == "update":
            identifier(args.id)
        origin = site_url(config.values["site_url"])
        path = f"/collections/{config.values['collection_id']}/items"
        path += "/live" if args.action == "create" else f"/{args.id}/live"
        if not args.execute:
            return {"dryRun": True, "method": "POST" if args.action == "create" else "PATCH",
                    "siteId": config.values["site_id"], "siteUrl": origin,
                    "endpoint": "https://api.webflow.com/v2" + path,
                    "payload": payload, "schemaValidation": "performed before execute"}
    api = Webflow(config)
    if args.action == "collections":
        return api.collections()
    if args.action == "status" and not config.values["collection_id"]:
        return api.collections()
    config.need("collection_id")
    collection = api.collection()
    if args.action in ("status", "fields"):
        return collection
    if args.action == "get":
        return api.item(args.id, args.live)
    if args.action == "items":
        require(1 <= args.limit <= 100 and args.offset >= 0, "--limit must be 1..100; --offset must be >=0")
        suffix = "/live" if args.live else ""
        return api.request("GET", f"/collections/{config.values['collection_id']}/items{suffix}?" +
                           urlencode({"limit": args.limit, "offset": args.offset}))
    current = api.item(args.id) if args.action == "update" else None
    validate_fields(config, collection, payload, current)
    # Schema reads precede the mutation, so a discovery failure cannot hide a completed creation.
    response = api.request("POST" if args.action == "create" else "PATCH", path, payload)
    if not isinstance(response.get("id"), str) or not response["id"]:
        raise Failure("Mutation returned no item ID; reconcile before retrying", response=response)
    if args.action == "update":
        if response["id"] != args.id:
            raise Failure("Mutation returned a different item ID; reconcile before retrying", response=response)
    warnings = []
    verified = None
    try:
        verified = api.item(response["id"], live=True)
    except Failure as exc:
        warnings.append({"verificationError": str(exc), **exc.details})
    observed = verified or response
    published = bool(observed.get("lastPublished")) and observed.get("isDraft") is not True and observed.get("isArchived") is not True
    if observed.get("fieldData", {}).get(config.values["content_field_slug"]) != payload["fieldData"][config.values["content_field_slug"]]:
        warnings.append("Stored body differs from submitted body; no rollback was performed")
    candidate = None
    slug = observed.get("fieldData", {}).get(config.values["slug_field_slug"])
    if origin and isinstance(slug, str) and collection.get("slug"):
        candidate = origin + "/" + quote(collection["slug"], safe="") + "/" + quote(slug, safe="")
    return {"remoteObjectId": response["id"], "status": "published" if published else "unverified",
            "remoteUrlCandidate": candidate, "response": response, "verified": verified, "warnings": warnings}


def main():
    parser = parser_for(__doc__, ("status", "collections", "fields", "items", "get", "create", "update"), FIELDS)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--live", action="store_true", help="Read live instead of staged items")
    args = parser.parse_args()
    try:
        config = Config(args, "WEBFLOW", FIELDS, DEFAULTS, ("api_token",), setup_guide=SETUP_GUIDE)
    except Failure as exc:
        print(json.dumps({"error": str(exc), **exc.details}))
        return 1
    return cli_main(run, args, config)


if __name__ == "__main__":
    sys.exit(main())
