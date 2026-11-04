import contextlib
from http.client import IncompleteRead
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib import error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_common as c


class CommonTests(unittest.TestCase):
    def test_config_per_field_priority_and_secure_atomic_save(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            path = Path(tmp) / "private" / "config.json"
            fields = ("host", "secret", "destination")
            parser = c.parser_for("test", ("status",), fields)
            args = parser.parse_args(["configure", "--config", str(path), "--host", "explicit"])
            with patch.dict(os.environ, {"TEST_SECRET": "env-secret"}):
                config = c.Config(args, "TEST", fields, {"destination": "default"}, ("secret",))
                config.configure(fields)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            args = parser.parse_args(["status", "--config", str(path), "--host", "override"])
            with patch.dict(os.environ, {"TEST_DESTINATION": "env-target"}):
                config = c.Config(args, "TEST", fields, {}, ("secret",))
            self.assertEqual(config.values, {"host": "override", "secret": "env-secret", "destination": "env-target"})
            self.assertNotIn("env-secret", json.dumps(config.redact({"message": "echo env-secret", "access_token": "token"})))

    def test_malformed_config_stops_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("broken", encoding="utf-8")
            args = c.parser_for("test", ("status",), ("secret",)).parse_args(["status", "--config", str(path)])
            with self.assertRaises(c.Failure):
                c.Config(args, "TEST", ("secret",), {}, ("secret",))
            self.assertEqual(path.read_text(), "broken")

    def test_redirect_refused(self):
        self.assertIsNone(c.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://evil.test"))

    def test_http_error_native_json_and_retry_after(self):
        exc = error.HTTPError("https://api.test", 429, "limited", {"Retry-After": "30"}, io.BytesIO(b'{"message":"slow down"}'))
        opener = MagicMock()
        opener.open.side_effect = exc
        with patch.object(c.request, "build_opener", return_value=opener), self.assertRaises(c.Failure) as ctx:
            c.http("POST", "https://api.test", {}, {"body": "hi"})
        self.assertEqual(ctx.exception.details["http_status"], 429)
        self.assertEqual(ctx.exception.details["retry_after"], "30")
        self.assertEqual(ctx.exception.details["response"], {"message": "slow down"})
        self.assertEqual(opener.open.call_count, 1)

    def test_transport_and_invalid_json_no_retry(self):
        for failure in (TimeoutError(), error.URLError("offline"), IncompleteRead(b"partial")):
            opener = MagicMock()
            opener.open.side_effect = failure
            with patch.object(c.request, "build_opener", return_value=opener), self.assertRaises(c.Failure):
                c.http("POST", "https://api.test", {}, {})
            self.assertEqual(opener.open.call_count, 1)
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = b"not json"
        with patch.object(c.request, "build_opener", return_value=opener), self.assertRaises(c.Failure):
            c.http("POST", "https://api.test", {}, {})
        self.assertEqual(opener.open.call_count, 1)

    def test_invalid_configuration_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            path = Path(tmp) / "config.json"
            args = c.parser_for("test", ("status",), ("host",)).parse_args(
                ["configure", "--config", str(path), "--host", "bad-host"])
            config = c.Config(args, "TEST", ("host",), {}, ())
            def validate(_):
                raise c.Failure("Invalid host")
            with self.assertRaises(c.Failure):
                config.configure(("host",), validate)
            self.assertFalse(path.exists())

    def test_exception_output_redacts_provider_echo(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            args = c.parser_for("test", ("status",), ("secret",)).parse_args(["status", "--config", str(Path(tmp) / "config")])
            config = c.Config(args, "TEST", ("secret",), {}, ("secret",))
            config.values["secret"] = "unique-secret"
            def run(*_):
                raise c.Failure("echo unique-secret", response={"access_token": "another-token"})
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = c.cli_main(run, args, config)
            self.assertEqual(code, 1)
            self.assertNotIn("unique-secret", output.getvalue())
            self.assertNotIn("another-token", output.getvalue())


if __name__ == "__main__":
    unittest.main()
