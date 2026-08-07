import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.request import urlopen


SCRIPT = Path(__file__).parents[1] / "scripts" / "tiktok_ads.py"
SPEC = importlib.util.spec_from_file_location("tiktok_ads_cli", SCRIPT)
CLI = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CLI)


class FakeResponse:
    status = 200

    def read(self):
        return b'{"code":0,"data":{"items":[]}}'


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.closed = False

    def request(self, method, path, body=None, headers=None):
        self.calls.append((method, path, body, headers))

    def getresponse(self):
        return FakeResponse()

    def close(self):
        self.closed = True


class FakeMultipartConnection:
    def __init__(self):
        self.method = None
        self.path = None
        self.headers = {}
        self.payload = bytearray()
        self.closed = False

    def putrequest(self, method, path):
        self.method = method
        self.path = path

    def putheader(self, key, value):
        self.headers[key] = value

    def endheaders(self):
        return

    def send(self, value):
        self.payload.extend(value)

    def getresponse(self):
        return FakeResponse()

    def close(self):
        self.closed = True


class FakeCallbackServer:
    def __init__(self, address, handler):
        self.address = address
        self.handler = handler
        self.callback_result = None
        self.closed = False

    def handle_request(self):
        self.callback_result = {"auth_code": "one-time-code"}

    def server_close(self):
        self.closed = True


class TikTokAdsTests(unittest.TestCase):
    def test_authorization_url_and_loopback_validation(self):
        url = CLI.build_authorization_url(
            "app-123",
            "http://127.0.0.1:8765/callback",
            "state-value",
            "campaign.read,ad.write",
        )
        self.assertIn("https://ads.tiktok.com/marketing_api/auth?", url)
        self.assertIn("app_id=app-123", url)
        self.assertIn("state=state-value", url)
        self.assertIn("scope=campaign.read%2Cad.write", url)
        with self.assertRaises(CLI.CliError):
            CLI.validate_redirect_uri("http://0.0.0.0:8765/callback")
        with self.assertRaises(CLI.CliError):
            CLI.validate_redirect_uri("https://127.0.0.1:8765/callback")

    def test_callback_wait_uses_loopback_server(self):
        ready = mock.Mock()
        code = CLI.wait_for_oauth_callback(
            "http://127.0.0.1:8765/callback",
            "correct-state",
            30,
            ready=ready,
            server_factory=FakeCallbackServer,
        )
        self.assertEqual(code, "one-time-code")
        ready.assert_called_once_with()

    def test_callback_state_mismatch_records_terminal_error(self):
        server = SimpleNamespace(
            callback_path="/callback",
            expected_state="correct-state",
            callback_result=None,
        )
        handler = object.__new__(CLI.OAuthCallbackHandler)
        handler.server = server
        handler.path = "/callback?state=wrong-state&auth_code=ignored"
        handler.send_page = mock.Mock()

        handler.do_GET()

        self.assertEqual(server.callback_result["error"], "state_mismatch")
        self.assertIn("state did not match", server.callback_result["error_description"])
        handler.send_page.assert_called_once_with(
            400,
            "Authorization rejected",
            "OAuth state did not match. Return to TikTok and try again.",
        )

    def test_callback_missing_auth_code_records_terminal_error(self):
        server = SimpleNamespace(
            callback_path="/callback",
            expected_state="correct-state",
            callback_result=None,
        )
        handler = object.__new__(CLI.OAuthCallbackHandler)
        handler.server = server
        handler.path = "/callback?state=correct-state"
        handler.send_page = mock.Mock()

        handler.do_GET()

        self.assertEqual(server.callback_result["error"], "missing_auth_code")
        self.assertIn("did not contain auth_code", server.callback_result["error_description"])
        handler.send_page.assert_called_once_with(
            400,
            "Authorization rejected",
            "The callback did not contain auth_code.",
        )

    @unittest.skipUnless(os.environ.get("TIKTOK_ADS_SOCKET_TEST") == "1", "requires loopback socket permission")
    def test_real_loopback_callback_server(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        redirect_uri = f"http://127.0.0.1:{port}/callback"
        outcome = {}

        def wait():
            try:
                outcome["code"] = CLI.wait_for_oauth_callback(redirect_uri, "state-value", 10)
            except Exception as exc:
                outcome["error"] = exc

        thread = threading.Thread(target=wait)
        thread.start()
        for _ in range(100):
            try:
                with urlopen(f"{redirect_uri}?auth_code=real-code&state=state-value", timeout=1) as response:
                    self.assertEqual(response.status, 200)
                break
            except OSError:
                time.sleep(0.02)
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)
        self.assertEqual(outcome.get("code"), "real-code")

    def test_exchange_auth_code_calls_official_endpoint(self):
        response = {"code": 0, "data": {"access_token": "issued-token", "advertiser_ids": ["123"]}}
        with mock.patch.object(CLI, "api_request", return_value=response) as request:
            data = CLI.exchange_auth_code("app-123", "secret-value", "one-time-code")
        self.assertEqual(data["access_token"], "issued-token")
        request.assert_called_once_with(
            "POST",
            "/open_api/v1.3/oauth2/access_token/",
            {"app_id": "app-123", "auth_code": "one-time-code", "secret": "secret-value"},
            access_token=None,
            timeout=180,
        )

    def test_refresh_short_term_token_calls_official_endpoint(self):
        response = {
            "code": 0,
            "data": {"access_token": "new-token", "refresh_token": "rotated-refresh", "expires_in": 86400},
        }
        with mock.patch.object(CLI, "api_request", return_value=response) as request:
            data = CLI.refresh_short_term_token("app-123", "secret-value", "old-refresh")
        self.assertEqual(data["access_token"], "new-token")
        request.assert_called_once_with(
            "POST",
            "/open_api/v1.3/tt_user/oauth2/refresh_token/",
            {
                "client_id": "app-123",
                "client_secret": "secret-value",
                "grant_type": "refresh_token",
                "refresh_token": "old-refresh",
            },
            access_token=None,
            timeout=180,
        )

    def test_get_request_encodes_nested_query_and_token_header(self):
        connection = FakeConnection()
        with mock.patch.object(CLI.http.client, "HTTPSConnection", return_value=connection):
            result = CLI.api_request(
                "GET",
                "/open_api/v1.3/campaign/get/",
                {"advertiser_id": "123", "filtering": {"campaign_ids": ["456"]}},
                "access-token",
            )
        self.assertEqual(result["code"], 0)
        method, path, body, headers = connection.calls[0]
        self.assertEqual(method, "GET")
        self.assertIn("advertiser_id=123", path)
        self.assertIn("filtering=", path)
        self.assertIsNone(body)
        self.assertEqual(headers["Access-Token"], "access-token")
        self.assertTrue(connection.closed)

    def test_multipart_upload_streams_file_to_official_host(self):
        with tempfile.TemporaryDirectory() as directory:
            upload = Path(directory) / "creative.mp4"
            upload.write_bytes(b"video-bytes")
            connection = FakeMultipartConnection()
            with mock.patch.object(CLI.http.client, "HTTPSConnection", return_value=connection):
                result = CLI.api_request(
                    "POST",
                    "/open_api/v1.3/file/video/ad/upload/",
                    {"advertiser_id": "123", "upload_type": "UPLOAD_BY_FILE"},
                    "access-token",
                    files={"video_file": upload},
                )
        self.assertEqual(result["code"], 0)
        self.assertEqual(connection.method, "POST")
        self.assertEqual(connection.path, "/open_api/v1.3/file/video/ad/upload/")
        self.assertEqual(connection.headers["Access-Token"], "access-token")
        self.assertIn("multipart/form-data", connection.headers["Content-Type"])
        self.assertIn(b"video-bytes", bytes(connection.payload))
        self.assertIn(b'filename="creative.mp4"', bytes(connection.payload))
        self.assertTrue(connection.closed)

    def test_rejects_non_official_or_out_of_version_paths(self):
        for path in (
            "https://example.com/open_api/v1.3/ad/get/",
            "/open_api/v1.2/ad/get/",
            "/open_api/v1.3/../secret",
            "/open_api/v1.3/%2e%2e/secret",
        ):
            with self.subTest(path=path):
                with self.assertRaises(CLI.CliError):
                    CLI.validate_api_path(path)

    def test_redacts_nested_secrets(self):
        value = {"access_token": "abc", "body": {"app_secret": "def", "name": "safe"}}
        self.assertEqual(
            CLI.redact(value),
            {"access_token": "[REDACTED]", "body": {"app_secret": "[REDACTED]", "name": "safe"}},
        )

    def test_secret_file_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "token"
            path.write_text("secret\n", encoding="utf-8")
            path.chmod(0o600)
            self.assertEqual(CLI.read_secret_file(str(path), "token"), "secret")
            path.chmod(0o644)
            with self.assertRaises(CLI.CliError):
                CLI.read_secret_file(str(path), "token")

    def test_output_is_owner_only_and_stdout_can_be_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            with mock.patch("builtins.print") as output:
                CLI.print_json(
                    {"access_token": "secret"},
                    str(path),
                    display_value={"access_token": "[REDACTED]"},
                )
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"access_token": "secret"})
            self.assertEqual(json.loads(output.call_args.args[0]), {"access_token": "[REDACTED]"})

    def test_saved_credentials_supply_access_token(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            CLI.write_json_securely(str(path), {"access_token": "saved-token", "app_id": "saved-app"})
            args = mock.Mock(access_token_file=None, credentials_file=str(path))
            with mock.patch.dict("os.environ", {"TIKTOK_ADS_ACCESS_TOKEN": ""}, clear=False):
                self.assertEqual(CLI.resolve_access_token(args), "saved-token")

    def test_advertisers_executes_with_app_credentials_without_access_token(self):
        args = SimpleNamespace(
            action="advertisers",
            method=None,
            path=None,
            params_json=None,
            params_file=None,
            file=[],
            request_timeout=180,
            dry_run=False,
            execute=False,
            output=None,
            app_id="app-123",
            app_secret_file=None,
            credentials_file=None,
            access_token_file=None,
        )
        response = {"code": 0, "data": {"list": []}}
        with mock.patch.dict("os.environ", {"TIKTOK_ADS_APP_SECRET": "secret-value"}, clear=False):
            with mock.patch.object(CLI, "resolve_access_token") as resolve_token:
                with mock.patch.object(CLI, "api_request", return_value=response) as request:
                    with mock.patch("builtins.print"):
                        self.assertEqual(CLI.command_call(args), 0)

        resolve_token.assert_not_called()
        request.assert_called_once_with(
            "GET",
            "/open_api/v1.3/oauth2/advertiser/get/",
            {"app_id": "app-123", "secret": "secret-value"},
            None,
            timeout=180,
            files={},
        )

    def test_authorize_saves_token_but_not_app_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials_path = Path(directory) / "credentials.json"
            args = mock.Mock(
                app_id="app-123",
                app_secret_file=None,
                credentials_file=str(credentials_path),
                redirect_uri="http://127.0.0.1:8765/callback",
                scope="campaign.read",
                timeout=300,
                request_timeout=180,
            )
            token_data = {"access_token": "issued-token", "refresh_token": "refresh-token"}
            with mock.patch.dict("os.environ", {"TIKTOK_ADS_APP_SECRET": "never-save-this"}, clear=False):
                with mock.patch.object(CLI, "wait_for_oauth_callback", return_value="one-time-code"):
                    with mock.patch.object(CLI, "exchange_auth_code", return_value=token_data):
                        with mock.patch("builtins.print"):
                            self.assertEqual(CLI.command_authorize(args), 0)
            saved = json.loads(credentials_path.read_text(encoding="utf-8"))
            self.assertEqual(credentials_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(saved["access_token"], "issued-token")
            self.assertEqual(saved["app_id"], "app-123")
            self.assertNotIn("secret", saved)
            self.assertNotIn("never-save-this", credentials_path.read_text(encoding="utf-8"))

    def test_refresh_token_rotates_and_saves_credentials_without_app_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials_path = Path(directory) / "credentials.json"
            CLI.write_json_securely(
                str(credentials_path),
                {"access_token": "old-token", "refresh_token": "old-refresh", "app_id": "app-123"},
            )
            args = mock.Mock(
                app_id=None,
                app_secret_file=None,
                credentials_file=str(credentials_path),
                request_timeout=180,
            )
            token_data = {
                "access_token": "new-token",
                "refresh_token": "rotated-refresh",
                "expires_in": 86400,
                "refresh_token_expires_in": 31536000,
            }
            with mock.patch.dict("os.environ", {"TIKTOK_ADS_APP_SECRET": "never-save-this"}, clear=False):
                with mock.patch.object(CLI, "refresh_short_term_token", return_value=token_data):
                    with mock.patch("builtins.print"):
                        self.assertEqual(CLI.command_refresh_token(args), 0)
            saved = json.loads(credentials_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["access_token"], "new-token")
            self.assertEqual(saved["refresh_token"], "rotated-refresh")
            self.assertIn("access_token_expires_at", saved)
            self.assertIn("refresh_token_expires_at", saved)
            self.assertIn("refreshed_at", saved)
            self.assertNotIn("secret", saved)
            self.assertNotIn("never-save-this", credentials_path.read_text(encoding="utf-8"))

    def test_refresh_token_requires_saved_refresh_token(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials_path = Path(directory) / "credentials.json"
            CLI.write_json_securely(str(credentials_path), {"access_token": "long-token", "app_id": "app-123"})
            args = mock.Mock(
                app_id=None,
                app_secret_file=None,
                credentials_file=str(credentials_path),
                request_timeout=180,
            )
            with self.assertRaisesRegex(CLI.CliError, "do not use refresh tokens"):
                CLI.command_refresh_token(args)

    def test_mutation_dry_runs_without_resolving_token(self):
        args = mock.Mock(
            action="campaign-create",
            method=None,
            path=None,
            params_json=json.dumps({"advertiser_id": "123", "campaign_name": "Launch"}),
            params_file=None,
            file=[],
            request_timeout=180,
            dry_run=False,
            execute=False,
            output=None,
        )
        with mock.patch.object(CLI, "resolve_access_token") as token:
            with mock.patch("builtins.print") as output:
                self.assertEqual(CLI.command_call(args), 0)
        token.assert_not_called()
        payload = json.loads(output.call_args.args[0])
        self.assertFalse(payload["executed"])
        self.assertTrue(payload["requires_execute"])
        self.assertEqual(payload["operation"]["method"], "POST")


if __name__ == "__main__":
    unittest.main()
