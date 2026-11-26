import io
import json
import os
import subprocess
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from ads_test_support import ROOT, LaunchCase

# isort: split
from ads_api import AdsError, AdsHTTPError
from ads_workflow import exclusive


class WorkflowTests(LaunchCase):
    def test_creative_only_card_from_cli_before_account_selection(self):
        self.input.write_text(
            json.dumps(
                {
                    "title": "Trail & road",
                    "body": 'A <script> with "quotes".',
                    "landing_page_url": "https://example.com/trail?a=1&b=2",
                    "image_url": "https://example.com/shoe.png?a=1&b=2",
                }
            )
        )
        output = self.work / "card.html"
        env = {k: v for k, v in os.environ.items() if not k.startswith("OPENAI_ADS_")}
        # An offline command must also work with an unrelated, unusable account selection.
        env["OPENAI_ADS_ACCOUNT_ID"] = "invalid/selection"
        result = subprocess.run(
            [
                "bash",
                str(ROOT / "scripts/chatgpt_ads.sh"),
                "preview-card",
                "--draft",
                str(self.input),
                "--output",
                str(output),
            ],
            check=True,
            env=env,
            capture_output=True,
        )
        self.assertEqual(json.loads(result.stdout), {"kind": "draft_card", "output": str(output)})
        card = output.read_text()
        self.assertIn("<h2>Trail &amp; road</h2>", card)
        self.assertIn("A &lt;script&gt; with &quot;quotes&quot;.", card)
        self.assertIn('href="https://example.com/trail?a=1&amp;b=2"', card)
        self.assertIn('src="https://example.com/shoe.png?a=1&amp;b=2"', card)
        self.assertEqual(set(self.work.iterdir()), {self.input, output})
        with self.assertRaises(ValueError):
            self.cli("execute", "--state", output, "--confirm", "yes")
        self.assertFalse(self.wire.calls)

    def test_full_draft_card_and_launch_use_the_same_asset_and_copy(self):
        del self.draft["image_url"]
        self.draft["file_id"] = "file_71"
        self.input.write_text(json.dumps(self.draft))
        output = self.work / "card.html"
        self.cli("preview-card", "--draft", self.input, "--output", output)
        self.assertFalse(self.wire.calls)
        html = output.read_text()
        self.assertNotIn("<img ", html)
        receipt = self.preview()["proposal"]
        for field in ("title", "body", "target_url"):
            self.assertIn(receipt["ad"]["creative"][field], html)
        self.assertIn(receipt["asset"]["file_id"], html)
        with self.assertRaises(FileExistsError):
            self.cli("preview-card", "--draft", self.input, "--output", self.state)
        self.assertEqual(self.cli("show", "--state", self.state)["proposal"], receipt)

    def test_invalid_card_creative_fails_without_output_or_network(self):
        output = self.work / "card.html"
        for change in (
            {"title": "x"},
            {"body": ""},
            {"landing_page_url": "javascript:alert(1)"},
            {"image_url": "file:///image"},
            {"file_id": "second_asset"},
            {"file_ids": ["a", "b"]},
        ):
            with self.subTest(change=change):
                self.input.write_text(json.dumps(dict(self.draft, **change)))
                with self.assertRaises(AdsError):
                    self.cli("preview-card", "--draft", self.input, "--output", output)
                self.assertFalse(output.exists())
        self.assertFalse(self.wire.calls)

    def test_scoped_403_guidance_through_read_commands(self):
        query = self.work / "account.json"
        query.write_text('{"ad_account_id":"adacct_7"}')
        for args, message, hint in (
            (
                ["get-ad-account-spend-limit-windows"],
                "User does not have access to the Ad Account.",
                "manage billing",
            ),
            (
                ["list-lead-sync-subscriptions", "--query", query],
                "Lead-sync subscriptions are not enabled for this ad account.",
                "ads-support@openai.com",
            ),
        ):
            with self.subTest(action=args[0]):
                failure = HTTPError(
                    "", 403, "Forbidden", {}, io.BytesIO(json.dumps({"error": {"message": message}}).encode())
                )
                with (
                    patch.object(self.wire, "open", side_effect=failure) as calls,
                    self.assertRaises(AdsHTTPError) as caught,
                ):
                    self.cli("read", *args)
                self.assertEqual(caught.exception.status, 403)
                self.assertIn(message, str(caught.exception))
                self.assertIn(hint, str(caught.exception))
                self.assertEqual(calls.call_count, 1)
                self.assertEqual(calls.call_args[0][0].method, "GET")

    def test_403_hints_preserve_private_errors_and_only_match_relevant_routes(self):
        for method, path, code, private, expect_limit, expect_leads in (
            ("POST", "/ad_account/daily_spend_limit/delete", 403, False, True, False),
            ("POST", "/ad_account/spend_limit_windows/w1", 403, False, True, False),
            ("DELETE", "/lead_sync_subscriptions/sub123", 403, True, False, True),
            ("GET", "/lead_sync_subscriptions", 401, False, False, False),
            ("GET", "/ad_account", 403, False, False, False),
        ):
            with self.subTest(path=path, status=code):
                failure = HTTPError("", code, "Rejected", {}, io.BytesIO(b"private detail fake-test-key"))
                with (
                    patch.object(self.wire, "open", side_effect=failure),
                    self.assertRaises(AdsHTTPError) as caught,
                ):
                    self.api.request(method, path, private=private)
                msg = str(caught.exception)
                self.assertEqual(caught.exception.status, code)
                self.assertNotIn("fake-test-key", msg)
                self.assertEqual("private detail" in msg, not private)
                self.assertEqual("manage billing" in msg, expect_limit)
                self.assertEqual("ads-support@openai.com" in msg, expect_leads)

    def test_preview_never_overwrites_existing_state(self):
        original = self.preview()
        with self.assertRaises(FileExistsError):
            self.preview(final_status="active")
        self.assertEqual(self.cli("show", "--state", self.state), original)

    def test_confirmation_draft_and_account_binding(self):
        p = self.preview()
        with self.assertRaises(AdsError):
            self.execute({"confirmation": "incorrect"})
        self.wire.account["id"] = "adacct_other"
        with self.assertRaisesRegex(AdsError, "Account"):
            self.execute(p)
        modified = json.loads(self.state.read_text())
        modified["proposal"]["final_status"] = "active"
        self.state.write_text(json.dumps(modified))
        with self.assertRaisesRegex(AdsError, "changed"):
            self.execute(p)
        self.assertFalse(self.wire.posts())

    def test_same_receipt_cannot_execute_concurrently(self):
        p = self.preview()
        with exclusive(self.state), self.assertRaisesRegex(AdsError, "Another execution"):
            self.execute(p)
        self.assertFalse(self.wire.posts())

    def test_lost_local_checkpoint_recovers_created_resource(self):
        p = self.preview()
        from ads_workflow import save_json

        def fail_save(path, state, **kwargs):
            if state["steps"].get("create_campaign") == "cmpn_1":
                raise OSError("disk full")
            save_json(path, state, **kwargs)

        with patch("ads_workflow.save_json", side_effect=fail_save), self.assertRaises(OSError):
            self.execute(p)
        self.assertEqual(self.cli("show", "--state", self.state)["steps"]["create_campaign"], "pending")
        self.assertEqual(self.execute(p)["resources"]["campaign"]["id"], "cmpn_1")
        self.assertEqual(len(self.wire.objects), 3)

    def test_report_preserves_native_metrics_and_paginates(self):
        self.wire.pages = [
            {"data": [{"spend": 3.21}], "has_more": True, "last_id": "opaque+/=&"},
            {"data": [{"spend": 0}], "has_more": False},
        ]
        out = self.work / "report.json"
        summary = self.cli(
            "report",
            "--scope",
            "campaign",
            "--id",
            "cmpn_1",
            "--level",
            "ad",
            "--granularity",
            "daily",
            "--since",
            "2026-09-01",
            "--until",
            "2026-09-07",
            "--output",
            out,
        )
        self.assertEqual(summary["rows"], 2)
        self.assertEqual(json.loads(out.read_text())["data"], [{"spend": 3.21}, {"spend": 0}])
        first, second = self.wire.calls[-2:]
        self.assertEqual(first[1], "/campaigns/cmpn_1/insights")
        self.assertEqual(second[4], dict(first[4], after=["opaque+/=&"]))
        self.assertIn("ad.ctr", first[4]["fields[]"])
        self.assertEqual(
            json.loads(first[4]["time_ranges[]"][0]),
            {
                "type": "date_range",
                "since": "2026-09-01",
                "until": "2026-09-07",
                "timezone": "America/Los_Angeles",
            },
        )

    def test_invalid_scope_and_interrupted_report_never_saves_partial_output(self):
        args = ["report", "--since", "2026-09-01", "--until", "2026-09-01"]
        with self.assertRaises(AdsError):
            self.cli(*args, "--scope", "ad", "--id", "ad_3", "--level", "campaign")
        with self.assertRaises(AdsError):
            self.cli(*args, "--scope", "ad")
        out = self.work / "report.json"
        for pages in (
            [{"data": [], "has_more": True}],
            [{"data": []}],
            [{"data": [], "has_more": True, "last_id": "stuck"}] * 2,
        ):
            self.wire.pages = list(pages)
            with self.assertRaises(AdsError):
                self.cli(*args, "--output", out)
            self.assertFalse(out.exists())

    def test_report_for_each_scope(self):
        for scope, path in (
            ("ad_account", "/ad_account"),
            ("campaign", "/campaigns/test"),
            ("ad_group", "/ad_groups/test"),
            ("ad", "/ads/test"),
        ):
            with self.subTest(scope=scope):
                self.wire.pages = [{"has_more": False, "data": []}]
                resource = [] if scope == "ad_account" else ["--id", "test"]
                result = self.cli(
                    "report",
                    "--since",
                    "2026-09-01",
                    "--until",
                    "2026-09-01",
                    "--scope",
                    scope,
                    "--granularity",
                    "none",
                    *resource,
                )
                self.assertEqual(result["data"], [])
                self.assertEqual(self.wire.calls[-1][1], path + "/insights")

    def test_http_error_redacts_credentials_and_propagates_status(self):
        failure = HTTPError(
            "https://api.ads.openai.com/v1/ad_account",
            403,
            "Forbidden",
            {},
            io.BytesIO(b"bad key fake-test-key"),
        )
        with patch.object(self.wire, "open", side_effect=failure), self.assertRaisesRegex(
            AdsError, "403.*redacted"
        ) as caught:
            self.cli("account")
        self.assertNotIn("fake-test-key", str(caught.exception))

    def test_wrapper_offline_and_missing_credentials(self):
        env = dict(os.environ, OPENAI_ADS_API_KEY="", PYTHONDONTWRITEBYTECODE="1")
        cmd = ["bash", str(ROOT / "scripts/chatgpt_ads.sh")]
        p = self.preview()
        shown = subprocess.run(
            [*cmd, "show", "--state", str(self.state)], env=env, capture_output=True, check=True
        )
        self.assertEqual(json.loads(shown.stdout), p)
        failed = subprocess.run([*cmd, "account"], env=env, capture_output=True, check=False)
        self.assertEqual(failed.returncode, 1)
        self.assertIn(b"OPENAI_ADS_API_KEY", failed.stderr)


if __name__ == "__main__":
    unittest.main()
