#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "publish_file.sh"


class MockState:
    custom_domain: object = "publish.example.com"
    api_payload: dict[str, object] | None = None
    upload_url_status = 200
    include_public_url = True
    public_url = "https://publish.example.com/content/demo-result-id"
    upload_url_raw_body: bytes | None = None
    returned_file_key = "agent/results/demo.html"
    upload_body = b""
    upload_content_type = ""
    authorization_on_upload: str | None = None
    subscription_requests = 0
    upload_url_requests = 0
    publish_status = 200
    publish_requests = 0
    publish_content_id = ""
    publish_op_type = ""
    publish_payload: dict[str, object] | None = None
    publish_authorization: str | None = None


class Handler(BaseHTTPRequestHandler):
    state = MockState()

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/subscriptions/user":
            self.state.subscription_requests += 1
            self.send_json(200, {"data": {"custom_domain": self.state.custom_domain}})
            return
        self.send_json(404, {"message": "not found"})

    def do_POST(self) -> None:
        if self.path == "/s3/custom-upload-url":
            self.state.upload_url_requests += 1
            length = int(self.headers.get("Content-Length", "0"))
            self.state.api_payload = json.loads(self.rfile.read(length))
            if self.state.upload_url_raw_body is not None:
                body = self.state.upload_url_raw_body
                self.send_response(self.state.upload_url_status)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            port = self.server.server_port
            payload = {
                "presigned_url": f"http://127.0.0.1:{port}/upload/put?signature=secret",
                "key": self.state.returned_file_key,
                "content_id": "result-id",
            }
            if self.state.include_public_url:
                payload["url"] = self.state.public_url
            self.send_json(self.state.upload_url_status, payload)
            return
        self.send_json(404, {"message": "not found"})

    def do_PUT(self) -> None:
        if self.path.startswith("/upload/put"):
            length = int(self.headers.get("Content-Length", "0"))
            self.state.upload_body = self.rfile.read(length)
            self.state.upload_content_type = self.headers.get("Content-Type", "")
            self.state.authorization_on_upload = self.headers.get("Authorization")
            self.send_response(200)
            self.end_headers()
            return
        parsed = urlsplit(self.path)
        if (
            parsed.path.startswith("/s3/content/")
            and parsed.path.endswith("/publish")
        ):
            self.state.publish_requests += 1
            parts = parsed.path.strip("/").split("/")
            self.state.publish_content_id = parts[-2]
            self.state.publish_op_type = parse_qs(parsed.query).get("op_type", [""])[0]
            length = int(self.headers.get("Content-Length", "0"))
            self.state.publish_payload = json.loads(self.rfile.read(length))
            self.state.publish_authorization = self.headers.get("Authorization")
            if 200 <= self.state.publish_status < 300:
                self.send_response(self.state.publish_status)
                self.end_headers()
            else:
                self.send_json(
                    self.state.publish_status,
                    {"message": "publish failed"},
                )
            return
        self.send_json(404, {"message": "not found"})


class PublishFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.api_base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self) -> None:
        Handler.state.custom_domain = "publish.example.com"
        Handler.state.api_payload = None
        Handler.state.upload_url_status = 200
        Handler.state.include_public_url = True
        Handler.state.public_url = "https://publish.example.com/content/demo-result-id"
        Handler.state.upload_url_raw_body = None
        Handler.state.returned_file_key = "agent/results/demo.html"
        Handler.state.upload_body = b""
        Handler.state.upload_content_type = ""
        Handler.state.authorization_on_upload = None
        Handler.state.subscription_requests = 0
        Handler.state.upload_url_requests = 0
        Handler.state.publish_status = 200
        Handler.state.publish_requests = 0
        Handler.state.publish_content_id = ""
        Handler.state.publish_op_type = ""
        Handler.state.publish_payload = None
        Handler.state.publish_authorization = None
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temp_dir.name) / "demo.html"
        self.file_path.write_text("<h1>Hello</h1>", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_script(
        self,
        *extra: str,
        include_agent_id: bool = True,
        env_overrides: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("FREVANA_TOKEN", None)
        env.pop("FREVANA_AGENT_ID", None)
        env.pop("CODEX_AGENT_ID", None)
        env.pop("FREVANA_TEAM_ID", None)
        env.pop("CODEX_TEAM_ID", None)
        env.pop("FREVANA_SESSION_ID", None)
        env.pop("CODEX_THREAD_ID", None)
        env.pop("CODEX_SESSION_ID", None)
        env.pop("FREVANA_PUBLISH_HISTORY_FILE", None)
        env["FREVANA_API_BASE_URL"] = self.api_base_url
        if env_overrides:
            env.update(env_overrides)
        command = [
            "bash",
            str(SCRIPT_PATH),
            "--file",
            str(self.file_path),
            "--token",
            "test-token",
        ]
        if include_agent_id:
            command.extend(["--agent-id", "agent-123"])
        command.extend(extra)
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    @staticmethod
    def parse_result(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        return json.loads(result.stdout)

    def test_put_upload_and_public_url(self) -> None:
        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.parse_result(result),
            {
                "url": "https://publish.example.com/content/demo-result-id",
                "file_key": "agent/results/demo.html",
                "content_id": "result-id",
            },
        )
        self.assertEqual(Handler.state.upload_body, b"<h1>Hello</h1>")
        self.assertEqual(Handler.state.upload_content_type, "text/html")
        self.assertIsNone(Handler.state.authorization_on_upload)
        self.assertEqual(Handler.state.publish_requests, 1)
        self.assertEqual(Handler.state.publish_content_id, "result-id")
        self.assertEqual(Handler.state.publish_op_type, "publish")
        self.assertEqual(
            Handler.state.publish_payload,
            {
                "title": "Hello",
                "publish_type": "custom_domain",
                "category": "agent_app_result",
            },
        )
        self.assertEqual(Handler.state.publish_authorization, "Bearer test-token")
        self.assertEqual(
            Handler.state.api_payload,
            {
                "file_extension": "html",
                "content_type": "text/html",
                "agent_id": "agent-123",
                "scene_type": "content_html",
                "publish_type": "custom_domain",
                "file_title": "Hello",
                "category": "agent_app_result",
            },
        )

    def test_explicit_title_overrides_article_title(self) -> None:
        result = self.run_script("--title", "Provided title")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Handler.state.api_payload["file_title"], "Provided title")

    def test_successful_publish_returns_metadata_without_saving_it(self) -> None:
        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.parse_result(result),
            {
                "url": "https://publish.example.com/content/demo-result-id",
                "file_key": "agent/results/demo.html",
                "content_id": "result-id",
            },
        )
        self.assertFalse((self.file_path.parent / ".frevana").exists())
        self.assertNotIn("test-token", result.stdout)
        self.assertNotIn("signature=secret", result.stdout)
        self.assertNotIn("presigned_url", result.stdout)

    def test_update_sends_previous_file_key_to_upload_url_api(self) -> None:
        Handler.state.returned_file_key = "agent/results/existing-content.html"
        result = self.run_script(
            "--file-key",
            "agent/results/existing-content.html",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            Handler.state.api_payload["file_key"],
            "agent/results/existing-content.html",
        )
        self.assertEqual(Handler.state.upload_body, b"<h1>Hello</h1>")
        self.assertEqual(Handler.state.publish_requests, 1)
        self.assertEqual(
            self.parse_result(result)["file_key"],
            "agent/results/existing-content.html",
        )

    def test_update_result_retains_previous_key_when_response_omits_it(self) -> None:
        Handler.state.returned_file_key = ""

        result = self.run_script(
            "--file-key",
            "agent/results/existing-content.html",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.parse_result(result)["file_key"],
            "agent/results/existing-content.html",
        )

    def test_empty_update_file_key_is_rejected_before_network_request(self) -> None:
        result = self.run_script("--file-key", "")

        self.assertEqual(result.returncode, 1)
        self.assertIn("requires the previous file_key", result.stderr)
        self.assertEqual(Handler.state.subscription_requests, 0)
        self.assertEqual(Handler.state.upload_url_requests, 0)

    def test_first_non_empty_html_h1_is_extracted(self) -> None:
        self.file_path.write_text(
            "<title>Fallback title</title><h1>  </h1><h1>Article title</h1>",
            encoding="utf-8",
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Handler.state.api_payload["file_title"], "Article title")

    def test_markdown_frontmatter_title_is_extracted(self) -> None:
        self.file_path = Path(self.temp_dir.name) / "article.md"
        self.file_path.write_text(
            "---\ntitle: Quarterly Growth Report\n---\n\n# Ignored heading\n",
            encoding="utf-8",
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            Handler.state.api_payload["file_title"],
            "Quarterly Growth Report",
        )

    def test_filename_is_used_when_content_has_no_title(self) -> None:
        self.file_path = Path(self.temp_dir.name) / "artifact.bin"
        self.file_path.write_bytes(b"\x00\x01\x02")

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Handler.state.api_payload["file_title"], "artifact")

    def test_missing_custom_domain_stops_before_upload_url_request(self) -> None:
        Handler.state.custom_domain = ""

        result = self.run_script()

        self.assertEqual(result.returncode, 3)
        self.assertIn("https://www.frevana.com/dashboard/domain", result.stderr)
        self.assertEqual(Handler.state.upload_url_requests, 0)
        self.assertEqual(Handler.state.publish_requests, 0)

    def test_file_key_builds_public_url_when_url_is_missing(self) -> None:
        Handler.state.include_public_url = False

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.parse_result(result)["url"],
            "https://publish.example.com/agent/results/demo.html",
        )
        self.assertEqual(Handler.state.publish_requests, 1)

    def test_public_url_without_scheme_uses_custom_domain_scheme(self) -> None:
        Handler.state.custom_domain = "https://wenjun.frevana.space"
        Handler.state.public_url = (
            "wenjun.frevana.space/content/codex-从代码补全到软件工程智能体"
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.parse_result(result)["url"],
            "https://wenjun.frevana.space/content/codex-从代码补全到软件工程智能体",
        )
        self.assertEqual(Handler.state.publish_requests, 1)

    def test_public_url_host_does_not_have_to_match_custom_domain(self) -> None:
        Handler.state.custom_domain = "https://wenjun.frevana.space"
        Handler.state.public_url = "public.frevana.space/content/result-id"

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.parse_result(result)["url"],
            "https://public.frevana.space/content/result-id",
        )
        self.assertEqual(Handler.state.publish_requests, 1)

    def test_upload_url_api_error_does_not_expose_presigned_url(self) -> None:
        Handler.state.upload_url_status = 500

        result = self.run_script()

        self.assertEqual(result.returncode, 1)
        self.assertIn("failed with HTTP 500", result.stderr)
        self.assertNotIn("presigned_url", result.stderr)
        self.assertNotIn("signature=secret", result.stderr)
        self.assertEqual(Handler.state.upload_body, b"")
        self.assertEqual(Handler.state.publish_requests, 0)

    def test_malformed_upload_url_response_does_not_expose_raw_body(self) -> None:
        Handler.state.upload_url_raw_body = (
            b"presigned_url=https://storage.example/upload?signature=secret"
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 1)
        self.assertIn("returned non-JSON response", result.stderr)
        self.assertNotIn("presigned_url", result.stderr)
        self.assertNotIn("signature=secret", result.stderr)
        self.assertEqual(Handler.state.upload_body, b"")
        self.assertEqual(Handler.state.publish_requests, 0)

    def test_missing_extension_is_rejected_before_network_request(self) -> None:
        no_extension = Path(self.temp_dir.name) / "artifact"
        no_extension.write_text("content", encoding="utf-8")
        self.file_path = no_extension

        result = self.run_script()

        self.assertEqual(result.returncode, 1)
        self.assertIn("must have an extension", result.stderr)
        self.assertEqual(Handler.state.subscription_requests, 0)
        self.assertEqual(Handler.state.upload_url_requests, 0)

    def test_session_id_and_fixed_agent_id_fallbacks(self) -> None:
        result = self.run_script(
            include_agent_id=False,
            env_overrides={"CODEX_THREAD_ID": "session-456"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Handler.state.api_payload["agent_id"], "frevana-publish")
        self.assertEqual(Handler.state.api_payload["team_id"], "session-456")

    def test_team_id_takes_precedence_over_session_id(self) -> None:
        result = self.run_script(
            "--team-id",
            "team-789",
            "--session-id",
            "session-456",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Handler.state.api_payload["team_id"], "team-789")

    def test_agent_and_team_ids_are_discovered_from_environment(self) -> None:
        result = self.run_script(
            include_agent_id=False,
            env_overrides={
                "CODEX_AGENT_ID": "agent-from-env",
                "FREVANA_TEAM_ID": "team-from-env",
                "CODEX_THREAD_ID": "session-ignored",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Handler.state.api_payload["agent_id"], "agent-from-env")
        self.assertEqual(Handler.state.api_payload["team_id"], "team-from-env")

    def test_publish_failure_does_not_return_public_url(self) -> None:
        Handler.state.publish_status = 500

        result = self.run_script()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn(
            "File uploaded, but Frevana S3 content publish API request failed",
            result.stderr,
        )
        self.assertEqual(Handler.state.upload_body, b"<h1>Hello</h1>")
        self.assertEqual(Handler.state.publish_requests, 1)
        self.assertFalse((self.file_path.parent / ".frevana").exists())


if __name__ == "__main__":
    unittest.main()
