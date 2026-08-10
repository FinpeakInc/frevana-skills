import importlib.util
import json
import os
import sys
import tempfile
import unittest
import urllib.request
from argparse import Namespace
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "unity_ads.py"
SPEC = importlib.util.spec_from_file_location("unity_ads", MODULE_PATH)
unity_ads = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = unity_ads
SPEC.loader.exec_module(unity_ads)


class UnityAdsTests(unittest.TestCase):
    def test_management_path_rejects_absolute_and_traversal(self):
        for value in (
            "https://evil.example/path",
            "/advertise/v1/organizations/1/apps",
            "apps/../organizations/2",
            "apps?id=1",
            "apps//campaigns",
        ):
            with self.subTest(value=value), self.assertRaises(unity_ads.CliError):
                unity_ads.validate_relative_management_path(value)

    def test_management_path_accepts_relative_official_path(self):
        value = "apps/5eb26a338a232100e4bb5893/campaigns"
        self.assertEqual(unity_ads.validate_relative_management_path(value), value)

    def test_service_basic_auth_is_base64_encoded(self):
        args = Namespace(key_id_file=None, service_secret_file=None, bearer_token_file=None)
        with mock.patch.dict(
            os.environ,
            {
                "UNITY_ADS_SERVICE_ACCOUNT_KEY_ID": "key-id",
                "UNITY_ADS_SERVICE_ACCOUNT_SECRET": "secret",
            },
            clear=True,
        ):
            headers = unity_ads.service_auth_headers(args)
        self.assertEqual(headers["Authorization"], "Basic a2V5LWlkOnNlY3JldA==")
        self.assertNotIn("secret", headers["Authorization"])

    def test_bearer_auth_takes_precedence(self):
        args = Namespace(key_id_file=None, service_secret_file=None, bearer_token_file=None)
        with mock.patch.dict(
            os.environ,
            {
                "UNITY_ADS_SERVICE_ACCOUNT_BEARER_TOKEN": "bearer-value",
                "UNITY_ADS_SERVICE_ACCOUNT_KEY_ID": "key-id",
                "UNITY_ADS_SERVICE_ACCOUNT_SECRET": "secret",
            },
            clear=True,
        ):
            headers = unity_ads.service_auth_headers(args)
        self.assertEqual(headers["Authorization"], "Bearer bearer-value")

    def test_secret_file_requires_owner_only_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            secret = Path(folder) / "secret"
            secret.write_text("value", encoding="utf-8")
            secret.chmod(0o644)
            with self.assertRaises(unity_ads.CliError):
                unity_ads.validate_secret_file(str(secret))
            secret.chmod(0o600)
            self.assertEqual(unity_ads.validate_secret_file(str(secret)), secret)

    def test_date_range_requires_timezone_and_order(self):
        with self.assertRaises(unity_ads.CliError):
            unity_ads.validate_range("2026-08-01", "2026-08-02")
        with self.assertRaises(unity_ads.CliError):
            unity_ads.validate_range("2026-08-02T00:00:00Z", "2026-08-01T00:00:00Z")
        unity_ads.validate_range("2026-08-01T00:00:00Z", "2026-08-02T00:00:00Z")

    def test_eof_marker_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.csv"
            report.write_bytes(
                b"timestamp,clicks\n2026-08-01,2\n#__EOF__,rows=1\n"
            )
            unity_ads.verify_eof_marker_file(report)
            report.write_bytes(b"timestamp,clicks\n2026-08-01,2\n")
            with self.assertRaises(unity_ads.CliError):
                unity_ads.verify_eof_marker_file(report)

    def test_cross_origin_redirect_strips_authorization(self):
        request = urllib.request.Request(
            "https://monetization.api.unity.com/report",
            headers={"Authorization": "Token top-secret"},
        )
        redirected = unity_ads.SafeRedirectHandler().redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://storage.example/report.csv",
        )
        self.assertIsNotNone(redirected)
        self.assertIsNone(redirected.get_header("Authorization"))

    def test_same_origin_redirect_preserves_authorization(self):
        request = urllib.request.Request(
            "https://services.api.unity.com/first",
            headers={"Authorization": "Bearer value"},
        )
        redirected = unity_ads.SafeRedirectHandler().redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://services.api.unity.com/second",
        )
        self.assertEqual(redirected.get_header("Authorization"), "Bearer value")

    def test_redirect_rejects_https_downgrade(self):
        request = urllib.request.Request("https://services.api.unity.com/first")
        with self.assertRaises(unity_ads.CliError):
            unity_ads.SafeRedirectHandler().redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "http://services.api.unity.com/second",
            )

    def test_known_action_renders_ids(self):
        args = Namespace(
            app_id="5eb26a338a232100e4bb5893",
            campaign_id="5eb26a338a232100e4bb6361",
            resource_id=None,
        )
        route = unity_ads.render_route(
            unity_ads.ACTIONS["get-budget"].route, args
        )
        self.assertEqual(
            route,
            "apps/5eb26a338a232100e4bb5893/campaigns/5eb26a338a232100e4bb6361/budget",
        )

    def test_mutation_preview_does_not_send_write(self):
        args = Namespace(
            organization_id="5772916123937",
            action="update-budget",
            method=None,
            path=None,
            app_id="5eb26a338a232100e4bb5893",
            campaign_id="5eb26a338a232100e4bb6361",
            resource_id=None,
            param=[],
            body_file=None,
            current_path=None,
            verify_path=None,
            verify_mode="present",
            execute=False,
            output=None,
            key_id_file=None,
            service_secret_file=None,
            bearer_token_file=None,
        )
        with tempfile.TemporaryDirectory() as folder:
            body = Path(folder) / "body.json"
            body.write_text(json.dumps({"daily": "100.00"}), encoding="utf-8")
            body.chmod(0o600)
            args.body_file = str(body)
            with mock.patch.dict(
                os.environ,
                {
                    "UNITY_ADS_SERVICE_ACCOUNT_KEY_ID": "key-id",
                    "UNITY_ADS_SERVICE_ACCOUNT_SECRET": "secret",
                },
                clear=True,
            ), mock.patch.object(
                unity_ads,
                "get_current_state",
                return_value=(200, {"daily": "50.00"}),
            ), mock.patch.object(unity_ads, "request") as request_mock, mock.patch(
                "builtins.print"
            ):
                unity_ads.run_management_call(args)
            request_mock.assert_not_called()

    def test_mutation_execute_writes_once_and_verifies(self):
        args = Namespace(
            organization_id="5772916123937",
            action="update-budget",
            method=None,
            path=None,
            app_id="5eb26a338a232100e4bb5893",
            campaign_id="5eb26a338a232100e4bb6361",
            resource_id=None,
            param=[],
            body_file=None,
            current_path=None,
            verify_path=None,
            verify_mode="present",
            execute=True,
            output=None,
            key_id_file=None,
            service_secret_file=None,
            bearer_token_file=None,
        )
        with tempfile.TemporaryDirectory() as folder:
            body = Path(folder) / "body.json"
            body.write_text(json.dumps({"daily": "100.00"}), encoding="utf-8")
            body.chmod(0o600)
            args.body_file = str(body)
            with mock.patch.dict(
                os.environ,
                {
                    "UNITY_ADS_SERVICE_ACCOUNT_KEY_ID": "key-id",
                    "UNITY_ADS_SERVICE_ACCOUNT_SECRET": "secret",
                },
                clear=True,
            ), mock.patch.object(
                unity_ads,
                "get_current_state",
                side_effect=[
                    (200, {"daily": "50.00"}),
                    (200, {"daily": "100.00"}),
                ],
            ) as current_mock, mock.patch.object(
                unity_ads,
                "request",
                return_value=unity_ads.Response(200, {}, b'{"daily":"100.00"}'),
            ) as request_mock, mock.patch("builtins.print"):
                unity_ads.run_management_call(args)
            self.assertEqual(current_mock.call_count, 2)
            self.assertEqual(request_mock.call_count, 1)
            self.assertEqual(request_mock.call_args.args[0], "PATCH")
            self.assertEqual(request_mock.call_args.kwargs["retries"], 0)

    def test_mutation_rejects_unchanged_verified_state(self):
        with self.assertRaises(unity_ads.CliError):
            unity_ads.verify_mutation_state(
                unity_ads.ACTIONS["update-budget"],
                "PATCH",
                {"daily": "100.00"},
                {"daily": "50.00"},
                "present",
            )

    def test_bid_deletion_verification_requires_absence(self):
        action = unity_ads.ACTIONS["update-cpi-bids"]
        with self.assertRaises(unity_ads.CliError):
            unity_ads.verify_mutation_state(
                action,
                "PATCH",
                [{"country": "US", "bid": None}],
                {"results": [{"country": "US", "bid": "0.20"}]},
                "present",
            )
        unity_ads.verify_mutation_state(
            action,
            "PATCH",
            [{"country": "US", "bid": None}],
            {"results": []},
            "present",
        )

    def test_money_verification_accepts_normalized_precision(self):
        unity_ads.verify_mutation_state(
            unity_ads.ACTIONS["update-budget"],
            "PATCH",
            {"daily": "100.0"},
            {"daily": "100.000", "spent": "2.00"},
            "present",
        )

    def test_campaign_null_attribution_allows_documented_inheritance(self):
        unity_ads.verify_mutation_state(
            unity_ads.ACTIONS["update-campaign"],
            "PATCH",
            {"name": "Campaign", "attributionClickUrl": None},
            {
                "name": "Campaign",
                "attributionClickUrl": "https://app.example/click",
            },
            "present",
        )

    def test_generic_list_verification_uses_results(self):
        unity_ads.verify_mutation_state(
            None,
            "PUT",
            [{"country": "US", "goal": "1.2"}],
            {"results": [{"country": "US", "goal": "1.2"}]},
            "present",
        )

    def test_stream_copy_never_requests_unbounded_read(self):
        class ChunkedResponse:
            def __init__(self):
                self.chunks = [b"first", b"second", b""]

            def read(self, size=-1):
                self.assert_size(size)
                return self.chunks.pop(0)

            @staticmethod
            def assert_size(size):
                if size < 0:
                    raise AssertionError("unbounded read")

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.bin"
            with output.open("wb") as stream:
                unity_ads.copy_response_stream(ChunkedResponse(), stream)
            self.assertEqual(output.read_bytes(), b"firstsecond")

    def test_stream_report_validates_then_atomically_replaces_output(self):
        class Response:
            status = 200

            def __init__(self):
                self.chunks = [
                    b"timestamp,clicks\n",
                    b"2026-08-01,2\n#__EOF__,rows=1\n",
                    b"",
                ]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size=-1):
                if size < 0:
                    raise AssertionError("unbounded read")
                return self.chunks.pop(0)

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.csv"
            output.write_text("old", encoding="utf-8")
            with mock.patch.object(
                unity_ads.API_OPENER, "open", return_value=Response()
            ):
                status = unity_ads.stream_report_request(
                    "https://services.api.unity.com/report",
                    {},
                    output,
                    False,
                    require_eof_marker=True,
                )
            self.assertEqual(status, 200)
            self.assertIn("#__EOF__,rows=1", output.read_text(encoding="utf-8"))
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_invalid_streamed_report_preserves_existing_output(self):
        class Response:
            status = 200

            def __init__(self):
                self.chunks = [b"timestamp,clicks\n2026-08-01,2\n", b""]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size=-1):
                return self.chunks.pop(0)

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.csv"
            output.write_text("old", encoding="utf-8")
            with mock.patch.object(
                unity_ads.API_OPENER, "open", return_value=Response()
            ), self.assertRaises(unity_ads.CliError):
                unity_ads.stream_report_request(
                    "https://services.api.unity.com/report",
                    {},
                    output,
                    False,
                    require_eof_marker=True,
                )
            self.assertEqual(output.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(folder).glob("*.tmp")), [])

    def test_default_output_names_do_not_collide(self):
        first = unity_ads.default_output("acquire-acquisitions", "csv")
        second = unity_ads.default_output("acquire-acquisitions", "csv")
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
