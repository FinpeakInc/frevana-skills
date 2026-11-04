import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import shopify_cms as m
from cms_common import Config, Failure, cli_main, parser_for

BODY = '  <p data-x="中">Hello &amp; 世界</p>\n\n'
BLOG = {"id": "gid://shopify/Blog/123", "handle": "news", "title": "News"}
ARTICLE = {"id": "gid://shopify/Article/456", "handle": "guide", "body": BODY,
           "isPublished": True, "blog": BLOG}


class ShopifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.transport = patch.object(m, "http", side_effect=AssertionError("Unexpected network request"))
        self.http = self.transport.start()
        self.addCleanup(self.transport.stop)

    def setup(self, action="create", execute=False, data=None, **values):
        path = Path(self.tmp.name) / "content.json"
        path.write_text(json.dumps(data or {"title": "Guide", "bodyHtml": BODY}), encoding="utf-8")
        parser = parser_for("test", ("status", "blogs", "articles", "get", "create", "update"), m.FIELDS)
        parser.add_argument("--after")
        options = [action, "--config", str(Path(self.tmp.name) / "config.json"),
                   "--data-file", str(path), "--id", "456"]
        if execute:
            options.append("--execute")
        args = parser.parse_args(options)
        config = Config(args, "SHOPIFY", m.FIELDS, m.DEFAULTS, ("client_secret",))
        config.values.update(store_domain="https://demo.myshopify.com/", client_id="client",
                             client_secret="private-secret", blog_id="123", **values)
        return args, config

    def responses(self, mutation=None, verification=None, current=None):
        def respond(method, url, headers, data=None, **kwargs):
            if url.endswith("/access_token"):
                self.assertEqual(method, "POST")
                self.assertTrue(kwargs["form"])
                self.assertIn("grant_type=client_credentials", data)
                return {"access_token": "temporary-access-token"}
            self.assertEqual(headers["X-Shopify-Access-Token"], "temporary-access-token")
            self.assertIn("/2026-04/graphql.json", url)
            query = data["query"]
            if "node(id:" in query:
                return {"data": {"node": BLOG}}
            if query.startswith("mutation"):
                op = "articleUpdate" if "articleUpdate" in query else "articleCreate"
                return {"data": {op: mutation if mutation is not None else {"article": ARTICLE, "userErrors": []}}}
            if "article(id:" in query:
                if isinstance(verification, Exception):
                    raise verification
                return {"data": {"article": current or verification or ARTICLE}}
            return {"data": {"shop": {"name": "Demo", "myshopifyDomain": "demo.myshopify.com"}}}
        self.http.side_effect = respond

    def mutations(self):
        return [call.args[3] for call in self.http.call_args_list
                if len(call.args) > 3 and isinstance(call.args[3], dict) and
                call.args[3].get("query", "").startswith("mutation")]

    def test_offline_preview_and_verbatim_body(self):
        args, config = self.setup()
        config.values["client_secret"] = ""
        result = m.run(args, config)
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["variables"]["article"]["body"], BODY)
        self.assertEqual(result["variables"]["article"]["author"], {"name": "Frevana"})
        self.http.assert_not_called()

    def test_execute_create_exchange_and_readback(self):
        args, config = self.setup(execute=True)
        self.responses()
        result = m.run(args, config)
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["remoteObjectId"], ARTICLE["id"])
        self.assertEqual(result["remoteUrlCandidate"], "https://demo.myshopify.com/blogs/news/guide")
        self.assertEqual(len(self.mutations()), 1)
        self.assertEqual(self.mutations()[0]["variables"]["article"]["body"], BODY)
        self.assertEqual(sum(c.args[1].endswith("/access_token") for c in self.http.call_args_list), 1)

    def test_update_exact_gid_does_not_replace_author_or_tags(self):
        args, config = self.setup("update", True)
        self.responses()
        m.run(args, config)
        variables = self.mutations()[0]["variables"]
        self.assertEqual(variables["id"], ARTICLE["id"])
        self.assertNotIn("author", variables["article"])
        self.assertNotIn("tags", variables["article"])

    def test_update_refuses_another_blog_before_mutation(self):
        args, config = self.setup("update", True)
        self.responses(current={**ARTICLE, "blog": {"id": "gid://shopify/Blog/999"}})
        with self.assertRaisesRegex(Failure, "different blog"):
            m.run(args, config)
        self.assertEqual(self.mutations(), [])

    def test_body_mismatch_is_warning_without_rollback(self):
        args, config = self.setup(execute=True)
        self.responses(verification={**ARTICLE, "body": "sanitized"})
        result = m.run(args, config)
        self.assertEqual(result["status"], "published")
        self.assertTrue(result["warnings"])
        self.assertEqual(len(self.mutations()), 1)

    def test_failed_verification_retains_receipt(self):
        args, config = self.setup(execute=True)
        self.responses(verification=Failure("read timed out"))
        result = m.run(args, config)
        self.assertEqual(result["remoteObjectId"], ARTICLE["id"])
        self.assertIsNone(result["verified"])
        self.assertIn("articleCreate", result["response"])
        self.assertEqual(len(self.mutations()), 1)

    def test_top_level_errors_stop(self):
        args, config = self.setup(execute=True)
        self.http.side_effect = [{"access_token": "token"}, {"errors": [{"message": "denied"}]}]
        with self.assertRaises(Failure) as ctx:
            m.run(args, config)
        self.assertIn("errors", ctx.exception.details["response"])
        self.assertEqual(self.http.call_count, 2)

    def test_user_errors_even_when_http_succeeds(self):
        args, config = self.setup(execute=True)
        self.responses(mutation={"article": None, "userErrors": [{"message": "denied", "field": ["title"]}]})
        with self.assertRaisesRegex(Failure, "mutation rejected"):
            m.run(args, config)
        self.assertEqual(len(self.mutations()), 1)

    def test_mutation_timeout_is_not_retried(self):
        args, config = self.setup(execute=True)
        self.http.side_effect = [{"access_token": "token"}, {"data": {"node": BLOG}}, Failure("timeout")]
        with self.assertRaises(Failure):
            m.run(args, config)
        self.assertEqual(len(self.mutations()), 1)

    def test_missing_id_preserves_native_response(self):
        args, config = self.setup(execute=True)
        self.responses(mutation={"article": {"handle": "guide"}, "userErrors": []})
        with self.assertRaises(Failure) as ctx:
            m.run(args, config)
        self.assertIn("articleCreate", ctx.exception.details["response"])

    def test_unpublished_result_exits_nonzero_with_id(self):
        args, config = self.setup(execute=True)
        unpublished = {**ARTICLE, "isPublished": False}
        self.responses(mutation={"article": unpublished}, verification=unpublished)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli_main(m.run, args, config), 1)
        self.assertEqual(json.loads(output.getvalue())["remoteObjectId"], ARTICLE["id"])

    def test_unknown_input_and_wrong_tags_fail_without_requests(self):
        for extra in ({"unknown": 1}, {"tags": "tag"}, {"summary": None}):
            args, config = self.setup(data={"title": "Guide", "bodyHtml": BODY, **extra})
            with self.assertRaises(Failure):
                m.run(args, config)
        self.http.assert_not_called()

    def test_host_and_gid_validation_prevents_token_to_other_hosts(self):
        for host in ("demo.myshopify.com.evil.test", "http://demo.myshopify.com", "demo.myshopify.com/path",
                     "user@demo.myshopify.com", "demo.myshopify.com:444"):
            with self.assertRaises(Failure):
                m.domain(host)
        with self.assertRaises(Failure):
            m.gid("Article", BLOG["id"])
        self.assertEqual(m.gid("Blog", "9007199254740993"), "gid://shopify/Blog/9007199254740993")

    def test_explicit_cursor_single_page(self):
        args, config = self.setup("articles")
        args.after = "verbatim==cursor"
        self.http.side_effect = [{"access_token": "token"}, {"data": {"blog": {"articles": {
            "nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "next"}}}}}]
        result = m.run(args, config)
        self.assertEqual(self.http.call_args.args[3]["variables"]["after"], args.after)
        self.assertTrue(result["blog"]["articles"]["pageInfo"]["hasNextPage"])
        self.assertEqual(self.http.call_count, 2)


if __name__ == "__main__":
    unittest.main()
