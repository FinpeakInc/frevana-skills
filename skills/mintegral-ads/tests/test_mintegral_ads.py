import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "mintegral_ads.py"
SPEC = importlib.util.spec_from_file_location("mintegral_ads", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class MintegralAdsTests(unittest.TestCase):
    def test_token_formula(self):
        timestamp = 1471256697
        api_key = "secret"
        inner = hashlib.md5(str(timestamp).encode()).hexdigest()
        expected = hashlib.md5((api_key + inner).encode()).hexdigest()
        self.assertEqual(MODULE.compute_token(api_key, timestamp), expected)

    def test_mutation_preview_needs_no_credentials_or_network(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(MODULE, "open_request") as mocked:
            code = MODULE.main(["call", "--action", "offer-status", "--params-json", '{"offer_id":1,"status":"STOPPED"}'])
        self.assertEqual(code, 0)
        mocked.assert_not_called()

    def test_invalid_offer_status_is_rejected(self):
        with self.assertRaises(MODULE.CliError):
            MODULE.main(["call", "--action", "offer-status", "--params-json", '{"offer_id":1,"status":"PAUSED"}'])

    def test_full_replacement_requires_acknowledgement(self):
        with self.assertRaisesRegex(MODULE.CliError, "acknowledge-full-replacement"):
            MODULE.main(["call", "--action", "offer-bid", "--params-json", '{"offer_id":1,"bid_rate":2}', "--execute"])

    def test_preflight_rejects_account_manager_owned_offer(self):
        response = {"code": 200, "data": {"list": [{"offer_id": 1, "maintain_by": "AM"}]}}
        with patch.dict(os.environ, {"MINTEGRAL_ACCESS_KEY": "access", "MINTEGRAL_API_KEY": "api"}, clear=True), patch.object(MODULE, "open_request", return_value=FakeResponse(response)) as mocked:
            with self.assertRaisesRegex(MODULE.CliError, "maintain_by=AM"):
                MODULE.main(["call", "--action", "offer-status", "--params-json", '{"offer_id":1,"status":"STOPPED"}', "--execute"])
        self.assertEqual(mocked.call_count, 1)

    def test_offer_status_executes_and_verifies(self):
        offer = {"code": 200, "data": {"list": [{"offer_id": 1, "maintain_by": "ADV", "status": "RUNNING"}]}}
        changed = {"code": 200, "msg": "success", "data": {}}
        verified = {"code": 200, "data": {"list": [{"offer_id": 1, "maintain_by": "ADV", "status": "STOPPED"}]}}
        with patch.dict(os.environ, {"MINTEGRAL_ACCESS_KEY": "access", "MINTEGRAL_API_KEY": "api"}, clear=True), patch.object(MODULE, "open_request", side_effect=[FakeResponse(offer), FakeResponse(changed), FakeResponse(verified)]) as mocked:
            code = MODULE.main(["call", "--action", "offer-status", "--params-json", '{"offer_id":1,"status":"STOPPED"}', "--execute"])
        self.assertEqual(code, 0)
        self.assertEqual(mocked.call_count, 3)
        methods = [call.args[0].method for call in mocked.call_args_list]
        self.assertEqual(methods, ["GET", "PUT", "GET"])

    def test_error_response_code_is_failure_even_on_http_success(self):
        response = {"code": 500, "msg": "bad token"}
        with patch.dict(os.environ, {"MINTEGRAL_ACCESS_KEY": "access", "MINTEGRAL_API_KEY": "api"}, clear=True), patch.object(MODULE, "open_request", return_value=FakeResponse(response)):
            with self.assertRaisesRegex(MODULE.CliError, "Mintegral API error"):
                MODULE.request_json(MODULE.ACTIONS["balance"], {})

    def test_authenticated_request_refuses_cross_host_redirect(self):
        handler = MODULE.RejectRedirects()
        request = MODULE.Request("https://ss-api.mintegral.com/start", headers={"access-key": "secret"})
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {"Location": "https://attacker.invalid/sink"},
            "https://attacker.invalid/sink",
        )
        self.assertIsNone(redirected)
        self.assertTrue(any(isinstance(item, MODULE.RejectRedirects) for item in MODULE.HTTP_OPENER.handlers))

    def test_full_replacement_preview_binds_state_and_payload(self):
        current = {"code": 200, "data": {"list": [{"offer_id": 1, "maintain_by": "ADV", "bid_rate": "2.0", "bid_rate_by_location": [{"country_code": "JP", "bid_rate": "3.0"}]}]}}
        stdout = StringIO()
        with patch.dict(os.environ, {"MINTEGRAL_ACCESS_KEY": "access", "MINTEGRAL_API_KEY": "api"}, clear=True), patch.object(MODULE, "open_request", return_value=FakeResponse(current)), redirect_stdout(stdout):
            code = MODULE.main(["call", "--action", "offer-bid", "--params-json", '{"offer_id":1,"bid_rate":2,"bid_rate_by_location":[{"country_code":"JP","bid_rate":3},{"country_code":"US","bid_rate":4.2}]}'])
        self.assertEqual(code, 0)
        preview = json.loads(stdout.getvalue())
        self.assertRegex(preview["replacement_plan_hash"], r"^[0-9a-f]{64}$")
        self.assertIn("before", preview)
        self.assertIn("replacement_diff", preview)

    def test_existing_output_is_forced_to_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text("old", encoding="utf-8")
            path.chmod(0o644)
            with redirect_stdout(StringIO()):
                MODULE.write_output({"code": 200}, str(path))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_changed_replacement_payload_cannot_reuse_preview_hash(self):
        current = {"code": 200, "data": {"list": [{"offer_id": 1, "maintain_by": "ADV", "bid_rate": "2.0", "bid_rate_by_location": []}]}}
        original = {"offer_id": 1, "bid_rate": 2.5, "bid_rate_by_location": []}
        plan_hash = MODULE.replacement_plan_hash("offer-bid", current["data"]["list"][0], original)
        changed = '{"offer_id":1,"bid_rate":9.9,"bid_rate_by_location":[]}'
        with patch.dict(os.environ, {"MINTEGRAL_ACCESS_KEY": "access", "MINTEGRAL_API_KEY": "api"}, clear=True), patch.object(MODULE, "open_request", return_value=FakeResponse(current)) as mocked:
            with self.assertRaisesRegex(MODULE.CliError, "plan hash mismatch"):
                MODULE.main([
                    "call", "--action", "offer-bid", "--params-json", changed,
                    "--acknowledge-full-replacement", "--replacement-plan-hash", plan_hash, "--execute",
                ])
        self.assertEqual(mocked.call_count, 1)

    def test_unchanged_replacement_plan_executes_and_verifies(self):
        before_item = {"offer_id": 1, "maintain_by": "ADV", "bid_rate": "2.0", "bid_rate_by_location": []}
        params = {"offer_id": 1, "bid_rate": 2.5, "bid_rate_by_location": []}
        plan_hash = MODULE.replacement_plan_hash("offer-bid", before_item, params)
        before = {"code": 200, "data": {"list": [before_item]}}
        changed = {"code": 200, "data": {}}
        after = {"code": 200, "data": {"list": [{**before_item, "bid_rate": "2.5"}]}}
        with patch.dict(os.environ, {"MINTEGRAL_ACCESS_KEY": "access", "MINTEGRAL_API_KEY": "api"}, clear=True), patch.object(MODULE, "open_request", side_effect=[FakeResponse(before), FakeResponse(changed), FakeResponse(after)]) as mocked, redirect_stdout(StringIO()):
            code = MODULE.main([
                "call", "--action", "offer-bid", "--params-json", json.dumps(params),
                "--acknowledge-full-replacement", "--replacement-plan-hash", plan_hash, "--execute",
            ])
        self.assertEqual(code, 0)
        self.assertEqual([call.args[0].method for call in mocked.call_args_list], ["GET", "PUT", "GET"])

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "O_NOFOLLOW is unavailable")
    def test_output_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.json"
            target.write_text("unchanged", encoding="utf-8")
            link = Path(directory) / "output.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(MODULE.CliError, "open --output safely"):
                MODULE.write_output({"code": 200}, str(link))
            self.assertEqual(target.read_text(encoding="utf-8"), "unchanged")

    def test_verification_reports_field_mismatch(self):
        current = {"code": 200, "data": {"list": [{"offer_id": 1, "maintain_by": "ADV", "status": "RUNNING"}]}}
        with patch.object(MODULE, "find_offer", return_value=current["data"]["list"][0]):
            verification = MODULE.verify(
                "offer-status",
                MODULE.ACTIONS["offer-status"],
                {"offer_id": 1, "status": "STOPPED"},
                {"code": 200, "data": {}},
            )
        self.assertFalse(verification["verified"])
        self.assertIn("status", verification["mismatches"])

    def test_offer_create_verifies_new_offer_not_parent_campaign(self):
        created_offer = {"offer_id": 77, "campaign_id": 5, "offer_name": "launch_1"}
        with patch.object(MODULE, "find_offer", return_value=created_offer) as find_offer, patch.object(MODULE, "find_campaign") as find_campaign:
            verification = MODULE.verify(
                "offer-create",
                MODULE.ACTIONS["offer-create"],
                {"campaign_id": 5, "offer_name": "launch_1"},
                {"code": 200, "data": {"offer_id": 77}},
            )
        self.assertTrue(verification["verified"])
        find_offer.assert_called_once_with(77)
        find_campaign.assert_not_called()

    def test_creative_set_delete_requires_exact_existing_target(self):
        offer = {"code": 200, "data": {"list": [{"offer_id": 1, "maintain_by": "ADV"}]}}
        missing_set = {"code": 200, "data": {"list": []}}
        with patch.dict(os.environ, {"MINTEGRAL_ACCESS_KEY": "access", "MINTEGRAL_API_KEY": "api"}, clear=True), patch.object(MODULE, "open_request", side_effect=[FakeResponse(offer), FakeResponse(missing_set)]) as mocked:
            with self.assertRaisesRegex(MODULE.CliError, "creative set"):
                MODULE.main([
                    "call", "--action", "creative-set-delete",
                    "--params-json", '{"offer_id":1,"creative_set_name":"missing"}',
                    "--confirm-delete", "--execute",
                ])
        self.assertEqual(mocked.call_count, 2)


if __name__ == "__main__":
    unittest.main()
