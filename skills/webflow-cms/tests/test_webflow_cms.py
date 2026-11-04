import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import webflow_cms as m
from cms_common import Config, Failure, parser_for

SITE = "580e63e98c9a982ac9b8b741"
COLLECTION = "580e63fc8c9a982ac9b8b745"
ITEM = "580e64008c9a982ac9b8b754"
BODY = '  <p data-x="中">Hello &amp; 世界</p>\n\n'
SCHEMA = {"id": COLLECTION, "slug": "articles", "fields": [
    {"slug": "name", "type": "PlainText", "isRequired": True},
    {"slug": "slug", "type": "PlainText", "isRequired": True},
    {"slug": "body", "type": "RichText", "isRequired": True},
    {"slug": "summary", "type": "PlainText"},
    {"slug": "author", "type": "Reference", "isRequired": True},
]}
LIVE = {"id": ITEM, "lastPublished": "2026-11-04T00:00:00Z", "isDraft": False, "isArchived": False,
        "fieldData": {"name": "Guide", "slug": "guide", "body": BODY, "author": ITEM}}


class WebflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        transport = patch.object(m, "http", side_effect=AssertionError("Unexpected network request"))
        self.http = transport.start()
        self.addCleanup(transport.stop)

    def setup(self, action="create", execute=False, data=None):
        path = Path(self.tmp.name) / "content.json"
        payload = {"title": "Guide", "slug": "guide", "bodyHtml": BODY, "fieldData": {"author": ITEM}}
        path.write_text(json.dumps(payload if data is None else data), encoding="utf-8")
        parser = parser_for("test", ("status", "collections", "fields", "items", "get", "create", "update"), m.FIELDS)
        parser.add_argument("--live", action="store_true")
        parser.add_argument("--offset", type=int, default=0)
        options = [action, "--config", str(Path(self.tmp.name) / "config.json"), "--data-file", str(path), "--id", ITEM]
        if execute:
            options.append("--execute")
        args = parser.parse_args(options)
        config = Config(args, "WEBFLOW", m.FIELDS, m.DEFAULTS, ("api_token",), setup_guide=m.SETUP_GUIDE)
        config.values.update(site_id=SITE, site_url="https://example.webflow.io/", api_token="private-token",
                             collection_id=COLLECTION, content_field_slug="body")
        return args, config

    def responses(self, schema=None, current=None, mutation=None, verified=None, collections=None):
        def respond(method, url, headers, data=None):
            self.assertEqual(headers["Authorization"], "Bearer private-token")
            if url.endswith("/collections"):
                return {"collections": [{"id": COLLECTION}]} if collections is None else collections
            if url.endswith("/collections/" + COLLECTION):
                return copy.deepcopy(schema if schema is not None else SCHEMA)
            if method in ("POST", "PATCH"):
                if isinstance(mutation, Exception):
                    raise mutation
                return copy.deepcopy(mutation if mutation is not None else LIVE)
            if url.endswith("/" + ITEM + "/live"):
                if isinstance(verified, Exception):
                    raise verified
                return copy.deepcopy(verified if verified is not None else LIVE)
            if url.endswith("/" + ITEM):
                return copy.deepcopy(current if current is not None else LIVE)
            return {"items": [], "pagination": {"limit": 50, "offset": 0, "total": 100}}
        self.http.side_effect = respond

    def writes(self):
        return [call for call in self.http.call_args_list if call.args[0] in ("POST", "PATCH")]

    def test_offline_preview_verbatim_dynamic_mapping(self):
        args, config = self.setup()
        config.values["api_token"] = ""
        result = m.run(args, config)
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["payload"]["fieldData"]["body"], BODY)
        self.assertFalse(result["payload"]["isDraft"])
        self.assertEqual(result["siteUrl"], "https://example.webflow.io")
        self.http.assert_not_called()

    def test_missing_site_url_stops_reads_previews_and_writes(self):
        for action in ("status", "collections", "fields", "items", "get", "create", "update"):
            for execute in (False, True):
                with self.subTest(action=action, execute=execute):
                    args, config = self.setup(action, execute)
                    config.values["site_url"] = ""
                    with self.assertRaisesRegex(Failure, "WEBFLOW_SITE_URL") as ctx:
                        m.run(args, config)
                    self.assertEqual(ctx.exception.details["setupGuide"], m.SETUP_GUIDE)
        self.http.assert_not_called()

    def test_configure_missing_site_url_does_not_save(self):
        args, config = self.setup("configure")
        config.values["site_url"] = ""
        with patch("cms_common.sys.stdin.isatty", return_value=False):
            with self.assertRaisesRegex(Failure, "WEBFLOW_SITE_URL"):
                m.run(args, config)
        self.assertFalse(config.path.exists())
        self.http.assert_not_called()

    def test_configure_prompts_for_and_saves_site_url(self):
        args, config = self.setup("configure")
        config.values["site_url"] = ""
        with patch("cms_common.sys.stdin.isatty", return_value=True), patch(
                "builtins.input", return_value=" https://example.webflow.io/ ") as prompt:
            m.run(args, config)
        self.assertEqual(prompt.call_args.args[0], "WEBFLOW_SITE_URL: ")
        self.assertEqual(json.loads(config.path.read_text())["site_url"], "https://example.webflow.io")
        self.http.assert_not_called()

    def test_invalid_site_url_blocks_api_requests(self):
        for action in ("status", "create", "update"):
            with self.subTest(action=action):
                args, config = self.setup(action, execute=True)
                config.values["site_url"] = "https://example.webflow.io/designer"
                with self.assertRaisesRegex(Failure, "HTTPS site origin"):
                    m.run(args, config)
        self.http.assert_not_called()

    def test_create_live_schema_first_and_readback(self):
        args, config = self.setup(execute=True)
        self.responses()
        result = m.run(args, config)
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["remoteObjectId"], ITEM)
        self.assertEqual(result["remoteUrlCandidate"], "https://example.webflow.io/articles/guide")
        self.assertEqual(len(self.writes()), 1)
        write = self.writes()[0]
        self.assertEqual(write.args[1], f"https://api.webflow.com/v2/collections/{COLLECTION}/items/live")
        self.assertEqual(write.args[3]["fieldData"]["body"], BODY)
        self.assertTrue(self.http.call_args.args[1].endswith(f"/items/{ITEM}/live"))
        self.assertEqual([c.args[0] for c in self.http.call_args_list], ["GET", "GET", "POST", "GET"])

    def test_update_partial_fields_preserves_required_existing_values(self):
        args, config = self.setup("update", True, {"title": "Guide", "slug": "guide", "bodyHtml": BODY})
        self.responses()
        m.run(args, config)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0].args[0], "PATCH")
        self.assertTrue(self.writes()[0].args[1].endswith(f"/items/{ITEM}/live"))
        self.assertNotIn("author", self.writes()[0].args[3]["fieldData"])

    def test_missing_required_field_prevents_write(self):
        args, config = self.setup(execute=True, data={"title": "Guide", "slug": "guide", "bodyHtml": BODY})
        self.responses()
        with self.assertRaisesRegex(Failure, "author"):
            m.run(args, config)
        self.assertEqual(self.writes(), [])

    def test_site_collection_mismatch_prevents_write(self):
        args, config = self.setup(execute=True)
        self.responses(collections={"collections": []})
        with self.assertRaisesRegex(Failure, "does not belong"):
            m.run(args, config)
        self.assertEqual(self.writes(), [])

    def test_content_mapping_requires_rich_text(self):
        args, config = self.setup(execute=True)
        schema = copy.deepcopy(SCHEMA)
        schema["fields"][2]["type"] = "PlainText"
        self.responses(schema=schema)
        with self.assertRaisesRegex(Failure, "RichText"):
            m.run(args, config)
        self.assertEqual(self.writes(), [])

    def test_unknown_and_uneditable_fields_prevent_write(self):
        for schema in ({**SCHEMA, "fields": SCHEMA["fields"][:-1]},
                       {**SCHEMA, "fields": [{**f, "isEditable": False} for f in SCHEMA["fields"]]}):
            args, config = self.setup(execute=True)
            self.responses(schema=schema)
            with self.assertRaises(Failure):
                m.run(args, config)
            self.assertEqual(self.writes(), [])

    def test_mapping_collision_and_unknown_input_fail_offline(self):
        for data in ({"title": "Guide", "slug": "guide", "bodyHtml": BODY, "oops": True},
                     {"title": "Guide", "slug": "guide", "bodyHtml": BODY, "fieldData": {"body": "override"}},
                     {"title": "Guide", "slug": "guide", "bodyHtml": BODY, "summary": "unmapped"}):
            args, config = self.setup(data=data)
            with self.assertRaises(Failure):
                m.run(args, config)
        self.http.assert_not_called()

    def test_summary_sent_only_with_mapping(self):
        args, config = self.setup(data={"title": "Guide", "slug": "guide", "bodyHtml": BODY, "summary": ""})
        config.values["summary_field_slug"] = "summary"
        self.assertEqual(m.run(args, config)["payload"]["fieldData"]["summary"], "")

    def test_write_timeout_no_replacement(self):
        args, config = self.setup(execute=True)
        self.responses(mutation=Failure("timeout"))
        with self.assertRaises(Failure):
            m.run(args, config)
        self.assertEqual(len(self.writes()), 1)

    def test_failed_readback_preserves_receipt_and_no_retry(self):
        args, config = self.setup(execute=True)
        self.responses(verified=Failure("read timed out"))
        result = m.run(args, config)
        self.assertEqual(result["remoteObjectId"], ITEM)
        self.assertEqual(result["response"], LIVE)
        self.assertIsNone(result["verified"])
        self.assertTrue(result["warnings"])
        self.assertEqual(len(self.writes()), 1)

    def test_not_draft_alone_does_not_prove_published(self):
        args, config = self.setup(execute=True)
        unpublished = {**LIVE, "lastPublished": None}
        self.responses(mutation=unpublished, verified=unpublished)
        self.assertEqual(m.run(args, config)["status"], "unverified")

    def test_missing_id_retains_native_response(self):
        args, config = self.setup(execute=True)
        self.responses(mutation={"fieldData": {"slug": "guide"}})
        with self.assertRaises(Failure) as ctx:
            m.run(args, config)
        self.assertIn("fieldData", ctx.exception.details["response"])
        self.assertEqual(len(self.writes()), 1)

    def test_body_mismatch_warns_without_rollback(self):
        args, config = self.setup(execute=True)
        self.responses(verified={**LIVE, "fieldData": {**LIVE["fieldData"], "body": "sanitized"}})
        result = m.run(args, config)
        self.assertEqual(result["status"], "published")
        self.assertTrue(result["warnings"])
        self.assertEqual(len(self.writes()), 1)

    def test_primary_locale_get_and_explicit_live_read(self):
        args, config = self.setup("get")
        self.responses()
        m.run(args, config)
        self.assertTrue(self.http.call_args.args[1].endswith(f"/items/{ITEM}"))
        args.live = True
        m.run(args, config)
        self.assertTrue(self.http.call_args.args[1].endswith(f"/items/{ITEM}/live"))

    def test_pagination_metadata_one_page(self):
        args, config = self.setup("items")
        args.offset = 50
        self.responses()
        result = m.run(args, config)
        self.assertEqual(result["pagination"]["total"], 100)
        self.assertIn("offset=50", self.http.call_args.args[1])
        self.assertEqual(self.http.call_count, 3)

    def test_invalid_ids_and_site_urls(self):
        for value in ("../abc", "abc?limit=100", "https://other.test"):
            with self.assertRaises(Failure):
                m.identifier(value)
        for value in ("", " ", "http://example.com", "https://user:secret@example.com", "https://example.com/path"):
            with self.assertRaises(Failure):
                m.site_url(value)


if __name__ == "__main__":
    unittest.main()
