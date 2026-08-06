#!/usr/bin/env python3

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

SCRIPT = Path(__file__).parents[1] / "scripts" / "sensortower.py"
SPEC = spec_from_file_location("sensortower_cli", SCRIPT)
MODULE = module_from_spec(SPEC)
assert SPEC.loader is not None, "Module spec loader is not available"
SPEC.loader.exec_module(MODULE)

RUNNER_SCRIPT = Path(__file__).parents[1] / "scripts" / "run.py"
RUNNER_SPEC = spec_from_file_location("sensortower_runner", RUNNER_SCRIPT)
RUNNER = module_from_spec(RUNNER_SPEC)
assert RUNNER_SPEC.loader is not None
RUNNER_SPEC.loader.exec_module(RUNNER)


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


class SensorTowerTests(unittest.TestCase):
    def parse(self, argv):
        return MODULE.build_parser(MODULE.dt.date(2026, 4, 1)).parse_args(argv)

    def test_skill_parser_builds_clean_country_array(self):
        args = MODULE.build_parser().parse_args(
            [
                "sales", "--app-id", "123", "--os", "ios",
                "--countries", "us, GB", "--start", "2026-01-01",
                "--end", "2026-01-31",
            ]
        )
        endpoint, params = MODULE.endpoint_and_params(args)
        self.assertEqual(endpoint, "/v1/ios/sales_report_estimates")
        self.assertEqual(params["countries[]"], ["US", "GB"])

    def test_http_error_never_exposes_token_or_url(self):
        token = "TOPSECRET"
        error_body = io.BytesIO(b'{"error":"TOPSECRET is invalid"}')
        error = HTTPError(
            f"https://api.sensortower.com/x?auth_token={token}",
            401,
            "Unauthorized",
            {},
            error_body,
        )

        def fail(*_args, **_kwargs):
            raise error

        with patch.dict(os.environ, {"SENSORTOWER_AUTH_TOKEN": token}):
            with self.assertRaises(MODULE.CliError) as caught:
                MODULE.request_json("/x", {}, opener=fail)
        message = str(caught.exception)
        self.assertNotIn(token, message)
        self.assertNotIn("auth_token", message)
        self.assertIn("[REDACTED]", message)

    def test_api_response_is_preserved(self):
        payload = {"data": {"nested": [1, 2, 3]}, "revenue": "unknown"}

        def success(*_args, **_kwargs):
            return Response(json.dumps(payload).encode())

        with patch.dict(os.environ, {"SENSORTOWER_AUTH_TOKEN": "token"}):
            result = MODULE.request_json("/x", {}, opener=success)
        self.assertEqual(result, payload)

    def test_date_order_is_rejected(self):
        with self.assertRaises(MODULE.CliError):
            MODULE.validate_date_range("2026-02-01", "2026-01-01")

    def test_output_file_matches_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "result.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                MODULE.write_output({"ok": True}, str(output))
            self.assertEqual(output.read_text(), stdout.getvalue())
            self.assertIn(str(output), stderr.getvalue())

    def test_every_action_builds_the_expected_endpoint(self):
        cases = [
            (["search", "--term", "Royal Match"], "/v1/unified/search_entities"),
            (
                [
                    "sales", "--app-id", "123", "--os", "android",
                    "--countries", "US", "--start", "2026-01-01",
                    "--end", "2026-01-31",
                ],
                "/v1/android/sales_report_estimates",
            ),
            (["top-charts", "--os", "ios"], "/v1/itunes/top_charts"),
            (
                [
                    "active-users", "--app-id", "123", "--os", "ios",
                    "--countries", "US", "--start", "2026-01-01",
                    "--end", "2026-01-31",
                ],
                "/v1/itunes/active_users",
            ),
            (["publisher-apps", "--publisher-id", "456"], "/v1/unified/publisher_apps"),
            (
                ["ad-intelligence", "--action", "top-advertisers"],
                "/v1/unified/ad_intel/top_advertisers",
            ),
        ]
        for argv, expected in cases:
            with self.subTest(action=argv[0]):
                endpoint, _params = MODULE.endpoint_and_params(self.parse(argv))
                self.assertEqual(endpoint, expected)

    def test_request_encodes_array_parameters_and_token(self):
        captured = {}

        def success(request, **_kwargs):
            captured["url"] = request.full_url
            return Response(b"{}")

        params = {"countries[]": ["US", "GB"], "app_ids[]": "123"}
        with patch.dict(os.environ, {"SENSORTOWER_AUTH_TOKEN": "secret"}):
            MODULE.request_json("/v1/ios/sales_report_estimates", params, opener=success)
        query = parse_qs(urlparse(captured["url"]).query)
        self.assertEqual(query["countries[]"], ["US", "GB"])
        self.assertEqual(query["app_ids[]"], ["123"])
        self.assertEqual(query["auth_token"], ["secret"])

    def test_ad_intelligence_requires_app_id_for_creatives(self):
        args = self.parse(["ad-intelligence", "--action", "creatives"])
        with self.assertRaises(MODULE.CliError):
            MODULE.endpoint_and_params(args)

    def test_missing_token_is_a_clean_nonzero_failure(self):
        stderr = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stderr(stderr):
            result = MODULE.main(["search", "--term", "Royal Match"])
        self.assertEqual(result, 1)
        self.assertIn("SENSORTOWER_AUTH_TOKEN is not set", stderr.getvalue())

    def test_invalid_country_is_rejected_by_argparse(self):
        parser = MODULE.build_parser()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "active-users", "--app-id", "123", "--os", "ios",
                    "--countries", "USA", "--start", "2026-01-01",
                    "--end", "2026-01-31",
                ]
            )

    def test_runner_skips_install_when_requirements_have_only_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            requirements = Path(directory) / "requirements.txt"
            requirements.write_text("# standard library only\n\n", encoding="utf-8")
            with patch.object(RUNNER.venv.EnvBuilder, "create") as create:
                result = RUNNER.ensure_runtime(requirements)
        self.assertEqual(result, Path(sys.executable))
        create.assert_not_called()

    def test_runner_installs_dependencies_once_in_an_isolated_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = root / "requirements.txt"
            requirements.write_text("example-package==1.2.3\n", encoding="utf-8")
            runtime_cache = root / "cache"

            def create_environment(path):
                python = RUNNER.venv_python(Path(path))
                python.parent.mkdir(parents=True, exist_ok=True)
                python.write_text("", encoding="utf-8")

            with patch.object(RUNNER.venv.EnvBuilder, "create", side_effect=create_environment) as create:
                with patch.object(RUNNER.subprocess, "run") as install:
                    first = RUNNER.ensure_runtime(requirements, runtime_cache=runtime_cache)
                    second = RUNNER.ensure_runtime(requirements, runtime_cache=runtime_cache)

        self.assertEqual(first, second)
        self.assertTrue(str(first).startswith(str(runtime_cache)))
        create.assert_called_once()
        install.assert_called_once()
        install_args = install.call_args.args[0]
        self.assertEqual(install_args[1:4], ["-m", "pip", "install"])
        self.assertIn("--require-hashes", install_args)
        self.assertIn(str(requirements), install_args)


if __name__ == "__main__":
    unittest.main()
