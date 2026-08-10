#!/usr/bin/env python3

import io
import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse


SCRIPT = Path(__file__).parents[1] / "scripts" / "moloco_ads.py"
SPEC = spec_from_file_location("moloco_ads", SCRIPT)
MODULE = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Headers(dict):
    def get_content_type(self):
        return self.get("Content-Type", "").split(";", 1)[0]


class Response:
    def __init__(self, body=b"{}", content_type="application/json", status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = Headers({"Content-Type": content_type, **(headers or {})})

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


class MolocoAdsTests(unittest.TestCase):
    def parse(self, argv):
        return MODULE.build_parser().parse_args(argv)

    def test_token_exchange_uses_api_key_body_and_owner_only_cache(self):
        captured = {}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache" / "token.json"

            def opener(request, **_kwargs):
                captured["url"] = request.full_url
                captured["body"] = json.loads(request.data)
                captured["authorization"] = request.get_header("Authorization")
                captured["version"] = request.get_header("Moloco-cloud-api-version")
                return Response(b'{"token":"issued-token","token_type":"AUTH_TOKEN"}')

            with mock.patch.dict(
                os.environ,
                {
                    "MOLOCO_ADS_API_KEY": "api-key-secret",
                    "MOLOCO_ADS_TOKEN_CACHE": str(cache),
                },
                clear=False,
            ):
                token = MODULE.issue_access_token(opener=opener, now=lambda: 1000.0)
                cached = json.loads(cache.read_text(encoding="utf-8"))

            self.assertEqual(token, "issued-token")
            self.assertEqual(captured["url"], "https://api.moloco.cloud/cm/v1/auth/tokens")
            self.assertEqual(captured["body"], {"api_key": "api-key-secret"})
            self.assertIsNone(captured["authorization"])
            self.assertEqual(captured["version"], "v1.10")
            self.assertNotIn("api-key-secret", json.dumps(cached))
            self.assertEqual(cached["token"], "issued-token")
            self.assertEqual(stat.S_IMODE(cache.stat().st_mode), 0o600)

    def test_cached_token_is_bound_to_api_key_and_expiry_margin(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "token.json"
            with mock.patch.dict(
                os.environ,
                {"MOLOCO_ADS_API_KEY": "key-a", "MOLOCO_ADS_TOKEN_CACHE": str(cache)},
                clear=False,
            ):
                MODULE.write_cached_token(
                    "token-a",
                    10_000,
                    MODULE.api_key_fingerprint("key-a"),
                )
                self.assertEqual(MODULE.read_cached_token(now=lambda: 1_000), "token-a")
                os.environ["MOLOCO_ADS_API_KEY"] = "key-b"
                self.assertIsNone(MODULE.read_cached_token(now=lambda: 1_000))
                os.environ["MOLOCO_ADS_API_KEY"] = "key-a"
                self.assertIsNone(MODULE.read_cached_token(now=lambda: 9_500))

                cache.chmod(0o644)
                self.assertIsNone(MODULE.read_cached_token(now=lambda: 1_000))

    def test_api_request_uses_fixed_origin_bearer_and_version_headers(self):
        captured = {}

        def opener(request, **_kwargs):
            captured["url"] = request.full_url
            captured["authorization"] = request.get_header("Authorization")
            captured["version"] = request.get_header("Moloco-cloud-api-version")
            return Response()

        with mock.patch.dict(os.environ, {"MOLOCO_ADS_API_KEY": "api-key"}, clear=False):
            MODULE.api_request(
                "GET",
                "/cm/v1/campaigns",
                params={"ad_account_id": "acct", "states": ["ACTIVE", "PAUSED"]},
                opener=opener,
                token_resolver=lambda **_kwargs: "access-token",
            )

        parsed = urlparse(captured["url"])
        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}", MODULE.API_ORIGIN)
        self.assertEqual(captured["authorization"], "Bearer access-token")
        self.assertEqual(captured["version"], "v1.10")
        self.assertNotIn("access-token", captured["url"])
        self.assertEqual(parse_qs(parsed.query)["states"], ["ACTIVE", "PAUSED"])

    def test_rejects_absolute_out_of_prefix_and_traversal_endpoints(self):
        invalid = [
            "https://evil.example/cm/v1/campaigns",
            "/open_api/v1.3/campaign/get/",
            "/cm/v1/../secrets",
            "/cm/v1/campaigns?ad_account_id=x",
        ]
        for endpoint in invalid:
            with self.subTest(endpoint=endpoint), self.assertRaises(MODULE.CliError):
                MODULE.validate_endpoint(endpoint)

    def test_401_refreshes_cached_token_once(self):
        calls = []
        tokens = []

        def resolver(force_refresh=False):
            token = "fresh-token" if force_refresh else "old-token"
            tokens.append((force_refresh, token))
            return token

        def opener(request, **_kwargs):
            calls.append(request.get_header("Authorization"))
            if len(calls) == 1:
                raise HTTPError(
                    request.full_url,
                    401,
                    "Unauthorized",
                    Headers({"Content-Type": "application/json"}),
                    io.BytesIO(b'{"message":"expired"}'),
                )
            return Response()

        with mock.patch.dict(os.environ, {"MOLOCO_ADS_API_KEY": "api-key"}, clear=False):
            MODULE.api_request(
                "GET",
                "/cm/v1/campaigns",
                opener=opener,
                token_resolver=resolver,
            )

        self.assertEqual(calls, ["Bearer old-token", "Bearer fresh-token"])
        self.assertEqual(tokens, [(False, "old-token"), (True, "fresh-token")])

    def test_401_refreshes_token_but_does_not_retry_an_unsafe_request(self):
        calls = []
        tokens = []

        def resolver(force_refresh=False):
            tokens.append(force_refresh)
            return "fresh-token" if force_refresh else "stale-token"

        def opener(request, **_kwargs):
            calls.append(request)
            raise HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                Headers({"Content-Type": "application/json"}),
                io.BytesIO(b'{"message":"expired"}'),
            )

        with mock.patch.dict(os.environ, {"MOLOCO_ADS_API_KEY": "api-key"}, clear=False):
            with self.assertRaises(MODULE.ApiHttpError) as caught:
                MODULE.api_request(
                    "PUT",
                    "/cm/v1/campaigns/cmp-1",
                    body={"enabling_state": "DISABLED"},
                    retry_safe=False,
                    opener=opener,
                    token_resolver=resolver,
                )
        self.assertEqual(len(calls), 1)
        self.assertEqual(tokens, [False, True])
        self.assertIn("was not retried", str(caught.exception))
        self.assertIn("rerun", str(caught.exception).lower())

    def test_analytics_read_retries_429_and_honors_retry_after(self):
        calls = []
        sleeps = []

        def opener(request, **_kwargs):
            calls.append(request)
            if len(calls) == 1:
                raise HTTPError(
                    request.full_url,
                    429,
                    "Too Many Requests",
                    Headers({"Retry-After": "3", "Content-Type": "application/json"}),
                    io.BytesIO(b'{"message":"quota"}'),
                )
            return Response()

        with mock.patch.dict(os.environ, {"MOLOCO_ADS_API_KEY": "api-key"}, clear=False):
            MODULE.api_request(
                "POST",
                "/cm/v1/analytics-detail",
                body={"ad_account_id": "acct"},
                retry_safe=True,
                opener=opener,
                sleeper=sleeps.append,
                token_resolver=lambda **_kwargs: "token",
            )

        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [3.0])

    def test_report_creation_is_not_automatically_retried(self):
        calls = []

        def opener(request, **_kwargs):
            calls.append(request)
            raise HTTPError(
                request.full_url,
                500,
                "Server Error",
                Headers({"Content-Type": "application/json"}),
                io.BytesIO(b'{"message":"temporary"}'),
            )

        with mock.patch.dict(os.environ, {"MOLOCO_ADS_API_KEY": "api-key"}, clear=False):
            with self.assertRaises(MODULE.ApiHttpError):
                MODULE.api_request(
                    "POST",
                    "/cm/v1/reports",
                    body={"ad_account_id": "acct"},
                    retry_safe=False,
                    opener=opener,
                    token_resolver=lambda **_kwargs: "token",
                )
        self.assertEqual(len(calls), 1)

    def test_download_does_not_forward_moloco_credentials(self):
        captured = {}

        def opener(request, **_kwargs):
            captured["authorization"] = request.get_header("Authorization")
            captured["version"] = request.get_header("Moloco-cloud-api-version")
            captured["url"] = request.full_url
            return Response(b"date,spend\n2026-08-01,1\n", "text/csv")

        response = MODULE.download_location(
            "https://storage.example/report.csv?signature=secret",
            "report download",
            opener=opener,
        )
        self.assertTrue(response.body.startswith(b"date,spend"))
        self.assertIsNone(captured["authorization"])
        self.assertIsNone(captured["version"])
        self.assertIn("signature=secret", captured["url"])

    def test_status_sanitization_removes_presigned_locations(self):
        sanitized = MODULE.sanitized_status(
            {
                "status": "READY",
                "location_csv": ["https://storage/one", "https://storage/two"],
                "location_json": "https://storage/report.json",
            }
        )
        self.assertEqual(
            sanitized,
            {"status": "READY", "available_files": {"csv": 2, "json": 1}},
        )
        self.assertNotIn("https://", json.dumps(sanitized))

    def test_analytics_payload_validates_range_limit_and_required_fields(self):
        args = self.parse(
            [
                "analytics-detail",
                "--ad-account-id", "acct",
                "--from", "2026-01-01",
                "--to", "2026-01-07",
                "--dimensions", "DATE,CAMPAIGN_ID",
                "--metrics", "SPEND,CLICKS",
                "--limit", "10000",
            ]
        )
        payload = MODULE.analytics_payload(args)
        self.assertEqual(payload["limit"], "10000")
        self.assertEqual(payload["date_range"]["start"], "2026-01-01")

        args.limit = 10001
        with self.assertRaises(MODULE.CliError):
            MODULE.analytics_payload(args)

        args.limit = None
        args.payload_json = '{"limit":20000}'
        with self.assertRaises(MODULE.CliError):
            MODULE.analytics_payload(args)

    def test_analytics_payload_rejects_more_than_184_days(self):
        args = self.parse(
            [
                "analytics-detail",
                "--ad-account-id", "acct",
                "--from", "2026-01-01",
                "--to", "2026-07-04",
                "--dimensions", "DATE",
                "--metrics", "SPEND",
            ]
        )
        with self.assertRaises(MODULE.CliError):
            MODULE.analytics_payload(args)

    def test_report_payload_validates_enum_and_31_day_range(self):
        valid = self.parse(
            [
                "report-create",
                "--ad-account-id", "acct",
                "--from", "2026-01-01",
                "--to", "2026-01-31",
                "--dimensions", "DATE,CAMPAIGN",
                "--optional-metrics", "ENGAGED_VIEWS",
            ]
        )
        self.assertEqual(MODULE.report_payload(valid)["dimensions"], ["DATE", "CAMPAIGN"])

        too_long = self.parse(
            [
                "report-create",
                "--ad-account-id", "acct",
                "--from", "2026-01-01",
                "--to", "2026-02-01",
                "--dimensions", "DATE",
            ]
        )
        with self.assertRaises(MODULE.CliError):
            MODULE.report_payload(too_long)

        valid.dimensions = ["NOT_REAL"]
        with self.assertRaises(MODULE.CliError):
            MODULE.report_payload(valid)

    def test_list_requires_ad_account_for_scoped_resources(self):
        args = self.parse(["list", "--resource", "campaigns"])
        with self.assertRaises(MODULE.CliError):
            MODULE.command_list(args)

    def test_create_preview_does_not_call_api(self):
        args = self.parse(
            [
                "create",
                "--resource", "product",
                "--ad-account-id", "acct",
                "--payload-json", '{"title":"Example","api_key":"must-hide"}',
            ]
        )
        output = io.StringIO()
        with mock.patch.object(MODULE, "api_json") as request, redirect_stdout(output):
            MODULE.command_mutation(args)
        request.assert_not_called()
        preview = json.loads(output.getvalue())
        self.assertTrue(preview["preview"])
        self.assertEqual(preview["method"], "POST")
        self.assertEqual(preview["payload"]["api_key"], "[REDACTED]")

    def test_create_preview_redacts_url_credentials_query_values_and_fragment(self):
        args = self.parse(
            [
                "create",
                "--resource", "tracking-link",
                "--ad-account-id", "acct",
                "--product-id", "product",
                "--payload-json",
                json.dumps(
                    {
                        "tracking_url": (
                            "https://alice:password@tracker.example/click"
                            "?token=secret-token&campaign=spring#private-fragment"
                        ),
                        "landing_page_url": "https://example.com/product",
                    }
                ),
            ]
        )
        output = io.StringIO()
        with mock.patch.object(MODULE, "api_json") as request, redirect_stdout(output):
            MODULE.command_mutation(args)

        request.assert_not_called()
        serialized = output.getvalue()
        preview = json.loads(serialized)
        tracking_url = preview["payload"]["tracking_url"]
        self.assertNotIn("alice", serialized)
        self.assertNotIn("password", serialized)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("spring", serialized)
        self.assertNotIn("private-fragment", serialized)
        self.assertIn("tracker.example/click", tracking_url)
        self.assertIn("?[REDACTED]", tracking_url)
        self.assertEqual(
            preview["payload"]["landing_page_url"],
            "https://example.com/product",
        )

    def test_parquet_log_creation_and_download_are_not_advertised(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.parse(
                    [
                        "log-create",
                        "--ad-account-id", "acct",
                        "--date", "2026-08-09",
                        "--type", "IMP",
                        "--format", "PARQUET",
                    ]
                )
            with self.assertRaises(SystemExit):
                self.parse(
                    ["log-download", "--log-id", "log-1", "--format", "parquet"]
                )

    def test_update_preview_reads_current_object_but_does_not_write(self):
        args = self.parse(
            [
                "update",
                "--resource", "campaign",
                "--id", "cmp-1",
                "--payload-json", '{"enabling_state":"DISABLED"}',
            ]
        )
        output = io.StringIO()
        with mock.patch.object(MODULE, "api_json", return_value={"id": "cmp-1"}) as request:
            with redirect_stdout(output):
                MODULE.command_mutation(args)
        request.assert_called_once_with("GET", "/cm/v1/campaigns/cmp-1", params={})
        preview = json.loads(output.getvalue())
        self.assertEqual(preview["current"], {"id": "cmp-1"})
        self.assertEqual(preview["method"], "PUT")

    def test_update_execute_returns_before_response_and_verified_after(self):
        args = self.parse(
            [
                "update",
                "--resource", "campaign",
                "--id", "cmp-1",
                "--payload-json", '{"enabling_state":"DISABLED"}',
                "--execute",
                "--stdout",
            ]
        )
        responses = iter(
            [
                {"campaign": {"id": "cmp-1", "enabling_state": "ENABLED"}},
                {"campaign": {"id": "cmp-1", "enabling_state": "DISABLED"}},
                {"campaign": {"id": "cmp-1", "enabling_state": "DISABLED"}},
            ]
        )
        output = io.StringIO()
        with mock.patch.object(MODULE, "api_json", side_effect=lambda *_a, **_k: next(responses)) as request:
            with redirect_stdout(output):
                MODULE.command_mutation(args)
        result = json.loads(output.getvalue())
        self.assertEqual(request.call_count, 3)
        self.assertEqual(result["before"]["campaign"]["enabling_state"], "ENABLED")
        self.assertEqual(result["after"]["campaign"]["enabling_state"], "DISABLED")

    def test_wait_with_stdout_is_rejected_before_report_creation(self):
        args = self.parse(
            [
                "report-create",
                "--ad-account-id", "acct",
                "--from", "2026-01-01",
                "--to", "2026-01-01",
                "--dimensions", "DATE",
                "--wait",
                "--stdout",
            ]
        )
        with mock.patch.object(MODULE, "api_json") as request:
            with self.assertRaises(MODULE.CliError):
                MODULE.command_report_create(args)
        request.assert_not_called()

    def test_saved_output_uses_owner_only_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            resolved = MODULE.write_bytes(path, b"{}\n")
            self.assertEqual(resolved, path.resolve())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_output_rejects_symlink_and_sanitizes_server_identifier(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.json"
            target.write_text("keep", encoding="utf-8")
            link = Path(directory) / "link.json"
            link.symlink_to(target)
            with self.assertRaises(MODULE.CliError):
                MODULE.write_bytes(link, b"replace")
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")

        generated = MODULE.output_path("report-../../escape", "json")
        self.assertEqual(generated.parent, Path.cwd() / "out")
        self.assertNotIn("..", generated.name)

    def test_download_preserves_gzip_suffix(self):
        status = {
            "status": "READY",
            "location_csv": ["https://storage.example/log-part.csv.gz?signature=secret"],
        }
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(
                MODULE,
                "download_location",
                return_value=MODULE.ApiResponse(b"compressed-bytes"),
            ):
                with mock.patch.object(MODULE.Path, "cwd", return_value=Path(directory)):
                    paths = MODULE.download_files(status, "csv", "log-safe", None)
            self.assertEqual(paths[0].suffixes, [".csv", ".gz"])
            self.assertEqual(paths[0].read_bytes(), b"compressed-bytes")

    def test_error_redacts_api_key_and_access_token(self):
        key = "TOP-SECRET-KEY"
        token = "TOP-SECRET-TOKEN"

        def opener(request, **_kwargs):
            raise HTTPError(
                request.full_url,
                400,
                "Bad Request",
                Headers({"Content-Type": "application/json"}),
                io.BytesIO(f'{{"message":"{key} {token}"}}'.encode()),
            )

        with mock.patch.dict(os.environ, {"MOLOCO_ADS_API_KEY": key}, clear=False):
            with self.assertRaises(MODULE.ApiHttpError) as caught:
                MODULE.api_request(
                    "GET",
                    "/cm/v1/campaigns",
                    opener=opener,
                    token_resolver=lambda **_kwargs: token,
                )
        message = str(caught.exception)
        self.assertNotIn(key, message)
        self.assertNotIn(token, message)
        self.assertIn("[REDACTED]", message)


if __name__ == "__main__":
    unittest.main()
