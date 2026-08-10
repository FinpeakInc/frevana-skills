#!/usr/bin/env python3

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

SCRIPT = Path(__file__).parents[1] / "scripts" / "appsflyer_reporting.py"
SPEC = spec_from_file_location("appsflyer_reporting", SCRIPT)
MODULE = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Headers(dict):
    def get_content_type(self):
        return self.get("Content-Type", "").split(";", 1)[0]


class Response:
    def __init__(self, body, content_type="text/csv"):
        self.body = body
        self.headers = Headers({"Content-Type": content_type})

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


class AppsFlyerReportingTests(unittest.TestCase):
    def parse(self, argv):
        return MODULE.build_parser().parse_args(argv)

    def test_date_ranges_are_split_into_inclusive_31_day_chunks(self):
        self.assertEqual(
            MODULE.date_chunks("2026-01-01", "2026-02-02"),
            [("2026-01-01", "2026-01-31"), ("2026-02-01", "2026-02-02")],
        )

    def test_reversed_date_range_is_rejected(self):
        with self.assertRaises(MODULE.CliError):
            MODULE.date_chunks("2026-02-01", "2026-01-01")

    def test_master_params_map_filters_and_calculated_kpi(self):
        args = self.parse(
            [
                "master-report",
                "--app-id", "com.example",
                "--from", "2026-01-01",
                "--to", "2026-01-01",
                "--groupings", "install_time,pid",
                "--kpis", "installs,revenue",
                "--campaign", "spring,summer",
                "--calculated-kpi", "calculated_kpi_rpi=revenue/installs",
                "--format", "json",
            ]
        )
        params = MODULE.master_params(args)
        self.assertEqual(params["groupings"], "install_time,pid")
        self.assertEqual(params["kpis"], "installs,revenue")
        self.assertEqual(params["c"], "spring,summer")
        self.assertEqual(params["calculated_kpi_rpi"], "revenue/installs")
        self.assertEqual(params["format"], "json")

    def test_all_pull_report_names_map_to_expected_paths(self):
        self.assertEqual(
            MODULE.PULL_REPORT_PATHS,
            {
                "partners": "partners_report",
                "partners-daily": "partners_by_date_report",
                "daily": "daily_report",
                "geo": "geo_report",
                "geo-daily": "geo_by_date_report",
            },
        )

    def test_master_execute_checks_freshness_and_uses_encoded_app_path(self):
        args = self.parse(
            [
                "master-report",
                "--app-id", "id/example",
                "--from", "2026-01-01",
                "--to", "2026-01-01",
                "--groupings", "install_time,pid",
                "--kpis", "installs",
            ]
        )
        stderr = io.StringIO()
        with patch.object(MODULE, "get_last_update", return_value=("2026-01-02", "text")):
            with patch.object(MODULE, "fetch_chunked_report", return_value="a,b\n1,2\n") as fetch:
                with redirect_stderr(stderr):
                    document, output_format, command = MODULE.execute(args)
        self.assertEqual(document, "a,b\n1,2\n")
        self.assertEqual(output_format, "csv")
        self.assertEqual(command, "master-report")
        self.assertEqual(fetch.call_args.args[0], "/api/master-agg-data/v4/app/id%2Fexample")
        self.assertIsNone(fetch.call_args.kwargs["chunk_days"])
        self.assertIn("2026-01-02", stderr.getvalue())

    def test_master_rejects_ranges_over_31_days_before_freshness_request(self):
        args = self.parse(
            [
                "master-report",
                "--app-id", "com.example",
                "--from", "2026-01-01",
                "--to", "2026-02-01",
                "--groupings", "pid",
                "--kpis", "installs",
            ]
        )
        with patch.object(MODULE, "get_last_update") as freshness:
            with self.assertRaises(MODULE.CliError) as caught:
                MODULE.execute(args)
        freshness.assert_not_called()
        self.assertIn("at most 31 inclusive days", str(caught.exception))

    def test_pull_execute_routes_report_and_converts_csv_to_json(self):
        args = self.parse(
            [
                "pull",
                "--report", "geo-daily",
                "--app-id", "com.example",
                "--from", "2026-01-01",
                "--to", "2026-01-01",
                "--format", "json",
            ]
        )
        with patch.object(
            MODULE, "fetch_chunked_report", return_value="date,country\n2026-01-01,US\n"
        ) as fetch:
            document, output_format, command = MODULE.execute(args)
        self.assertEqual(
            fetch.call_args.args[0],
            "/api/agg-data/export/app/com.example/geo_by_date_report/v5",
        )
        self.assertEqual(json.loads(document), [{"date": "2026-01-01", "country": "US"}])
        self.assertEqual(output_format, "json")
        self.assertEqual(command, "pull-geo-daily")
        self.assertEqual(fetch.call_args.kwargs["chunk_days"], 31)

    def test_non_daily_pull_report_is_sent_as_one_aggregate_request(self):
        args = self.parse(
            [
                "pull",
                "--report", "partners",
                "--app-id", "com.example",
                "--from", "2026-01-01",
                "--to", "2026-04-30",
            ]
        )
        with patch.object(
            MODULE, "fetch_chunked_report", return_value="campaign,installs\nSpring,1\n"
        ) as fetch:
            MODULE.execute(args)
        self.assertIsNone(fetch.call_args.kwargs["chunk_days"])

    def test_request_uses_bearer_header_and_not_query_token(self):
        captured = {}

        def success(request, **_kwargs):
            captured["url"] = request.full_url
            captured["authorization"] = request.get_header("Authorization")
            return Response(b"{}", "application/json")

        with patch.dict(os.environ, {"APPSFLYER_API_TOKEN": "secret"}):
            MODULE.request_api(
                "/api/test", {"from": "2026-01-01"}, accept="application/json", opener=success
            )
        self.assertEqual(captured["authorization"], "Bearer secret")
        self.assertNotIn("secret", captured["url"])
        self.assertNotIn("token", parse_qs(urlparse(captured["url"]).query))

    def test_http_error_redacts_token_and_adds_revocation_hint(self):
        token = "TOPSECRET"
        error = HTTPError(
            "https://hq1.appsflyer.com/api/test",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'TOPSECRET invalid'),
        )

        def fail(*_args, **_kwargs):
            raise error

        with patch.dict(os.environ, {"APPSFLYER_API_TOKEN": token}):
            with self.assertRaises(MODULE.CliError) as caught:
                MODULE.request_api("/api/test", accept="application/json", opener=fail)
        message = str(caught.exception)
        self.assertNotIn(token, message)
        self.assertIn("[REDACTED]", message)
        self.assertIn("2026-03-10", message)

    def test_429_retries_and_honors_retry_after(self):
        calls = []
        sleeps = []

        def flaky(*_args, **_kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise HTTPError(
                    "https://hq1.appsflyer.com/api/test",
                    429,
                    "Too Many Requests",
                    {"Retry-After": "3"},
                    io.BytesIO(b"limited"),
                )
            return Response(b"{}", "application/json")

        with patch.dict(os.environ, {"APPSFLYER_API_TOKEN": "secret"}):
            result = MODULE.request_api(
                "/api/test",
                accept="application/json",
                opener=flaky,
                sleeper=sleeps.append,
            )
        self.assertEqual(result.body, b"{}")
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [3.0])

    def test_chunked_csv_is_merged_with_one_header(self):
        responses = iter(
            [
                MODULE.ApiResponse(b"date,installs\n2026-01-01,1\n", "text/csv"),
                MODULE.ApiResponse(b"date,installs\n2026-02-01,2\n", "text/csv"),
            ]
        )
        captured = []

        def requester(endpoint, params, **_kwargs):
            captured.append((endpoint, params))
            return next(responses)

        result = MODULE.fetch_chunked_report(
            "/api/report",
            {"currency": "USD"},
            "2026-01-01",
            "2026-02-01",
            response_format="csv",
            requester=requester,
        )
        self.assertEqual(result.count("date,installs"), 1)
        self.assertIn("2026-01-01,1", result)
        self.assertIn("2026-02-01,2", result)
        self.assertEqual(captured[0][1]["to"], "2026-01-31")
        self.assertEqual(captured[1][1]["from"], "2026-02-01")

    def test_chunked_json_arrays_are_merged(self):
        result = MODULE.merge_json_documents(["[{\"id\": 1}]", "[{\"id\": 2}]"], "/x")
        self.assertEqual(json.loads(result), [{"id": 1}, {"id": 2}])

    def test_report_content_type_must_match_requested_format(self):
        with self.assertRaises(MODULE.CliError) as caught:
            MODULE.fetch_chunked_report(
                "/api/report",
                {},
                "2026-01-01",
                "2026-01-01",
                response_format="csv",
                requester=lambda *_args, **_kwargs: MODULE.ApiResponse(
                    b'{"error":"not a report"}', "application/json"
                ),
            )
        self.assertIn("expected a CSV report", str(caught.exception))

    def test_pull_csv_can_be_converted_to_json(self):
        result = MODULE.csv_to_json('date,campaign\n2026-01-01,"Spring, Sale"\n')
        self.assertEqual(
            json.loads(result),
            [{"date": "2026-01-01", "campaign": "Spring, Sale"}],
        )

    def test_last_update_accepts_plain_text(self):
        value, value_format = MODULE.parse_last_update(
            MODULE.ApiResponse(b"2026-08-09 12:00:00", "text/plain"), "/lastupdate"
        )
        self.assertEqual(value, "2026-08-09 12:00:00")
        self.assertEqual(value_format, "text")

    def test_output_is_saved_without_printing_report_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "report.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                MODULE.write_output('{"ok": true}\n', str(output), "test", "json")
            self.assertEqual(output.read_text(), '{"ok": true}\n')
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn(str(output), stderr.getvalue())

    def test_stdout_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.csv"
            stdout = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
                MODULE.write_output(
                    "a,b\n1,2\n", str(output), "test", "csv", stdout=True
                )
            self.assertEqual(stdout.getvalue(), "a,b\n1,2\n")

    def test_twitter_is_not_advertised_as_a_verified_category(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse(
                [
                    "pull",
                    "--report", "daily",
                    "--app-id", "com.example",
                    "--from", "2026-01-01",
                    "--to", "2026-01-01",
                    "--category", "twitter",
                ]
            )

    def test_missing_token_is_a_clean_failure(self):
        stderr = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stderr(stderr):
            result = MODULE.main(["master-last-update"])
        self.assertEqual(result, 1)
        self.assertIn("APPSFLYER_API_TOKEN is not set", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
