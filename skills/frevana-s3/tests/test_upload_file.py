#!/usr/bin/env python3

import json
import os
import subprocess
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "upload_file.sh"

class MockServerState:
    def __init__(self):
        self.upload_url_requests = []
        self.s3_upload_requests = []
        self.s3_upload_body = None

class MockHandler(BaseHTTPRequestHandler):
    state = MockServerState()

    def do_POST(self):
        if self.path == "/s3/custom-upload-url":
            length = int(self.headers.get("content-length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            auth = self.headers.get("authorization", "")
            self.state.upload_url_requests.append({
                "body": body,
                "auth": auth,
            })
            resp = {
                "presigned_url": f"http://127.0.0.1:{self.server.server_port}/mock-s3/upload?token=abc",
                "key": body.get("file_key") or "images-dev/user123/uploaded_test.png",
                "url": "https://cdn.example.com/images-dev/user123/uploaded_test.png",
                "content_id": "content_id_12345",
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        if self.path.startswith("/mock-s3/upload"):
            length = int(self.headers.get("content-length", 0))
            data = self.rfile.read(length)
            self.state.s3_upload_requests.append({
                "content_type": self.headers.get("content-type"),
                "auth": self.headers.get("authorization"),
            })
            self.state.s3_upload_body = data
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

class TestFrevanaS3Upload(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_file = Path(self.tmp_dir.name) / "sample_image.png"
        self.test_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRsample")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def run_script(self, args, env=None, check=True):
        cmd = [str(SCRIPT_PATH)] + args
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=merged_env,
            check=check,
        )

    def test_help(self):
        res = self.run_script(["--help"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("--file", res.stdout)
        self.assertIn("--file-key", res.stdout)
        self.assertIn("scene_type=universal", res.stdout)

    def test_missing_file(self):
        res = self.run_script([], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Missing required argument: --file", res.stderr)

    def test_dry_run_defaults(self):
        res = self.run_script(["--file", str(self.test_file), "--dry-run"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["file_extension"], "png")
        self.assertEqual(data["content_type"], "image/png")
        self.assertEqual(data["scene_type"], "universal")
        self.assertEqual(data["file_title"], "sample_image")
        self.assertNotIn("file_key", data)
        self.assertNotIn("agent_id", data)

    def test_dry_run_with_file_key_and_metadata(self):
        res = self.run_script([
            "--file", str(self.test_file),
            "--file-key", "images/prev.png",
            "--title", "Custom Title",
            "--category", "report",
            "--tags", "finance,q3",
            "--publish-type", "only_share_link",
            "--dry-run",
        ])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["file_key"], "images/prev.png")
        self.assertEqual(data["file_title"], "Custom Title")
        self.assertEqual(data["category"], "report")
        self.assertEqual(data["tags"], ["finance", "q3"])
        self.assertEqual(data["publish_type"], "only_share_link")

    def test_full_upload_flow(self):
        MockHandler.state = MockServerState()
        server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
        port = server.server_port
        t = Thread(target=server.serve_forever, daemon=True)
        t.start()

        try:
            res = self.run_script([
                "--file", str(self.test_file),
                "--token", "test_frevana_token_123",
                "--api-base-url", f"http://127.0.0.1:{port}",
            ])
            self.assertEqual(res.returncode, 0)
            data = json.loads(res.stdout)
            self.assertEqual(data["url"], "https://cdn.example.com/images-dev/user123/uploaded_test.png")
            self.assertEqual(data["content_id"], "content_id_12345")

            # Verify API request received by mock
            self.assertEqual(len(MockHandler.state.upload_url_requests), 1)
            api_req = MockHandler.state.upload_url_requests[0]
            self.assertEqual(api_req["auth"], "Bearer test_frevana_token_123")
            self.assertEqual(api_req["body"]["scene_type"], "universal")
            self.assertEqual(api_req["body"]["file_extension"], "png")

            # Verify S3 upload received
            self.assertEqual(len(MockHandler.state.s3_upload_requests), 1)
            s3_req = MockHandler.state.s3_upload_requests[0]
            self.assertEqual(s3_req["content_type"], "image/png")
            # CRITICAL: Verify Bearer token was NOT leaked to S3
            self.assertIsNone(s3_req["auth"])
            self.assertEqual(MockHandler.state.s3_upload_body, self.test_file.read_bytes())
        finally:
            server.shutdown()
            server.server_close()

    def test_text_only_output(self):
        MockHandler.state = MockServerState()
        server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
        port = server.server_port
        t = Thread(target=server.serve_forever, daemon=True)
        t.start()

        try:
            res = self.run_script([
                "--file", str(self.test_file),
                "--token", "test_token",
                "--api-base-url", f"http://127.0.0.1:{port}",
                "--text-only",
            ])
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout.strip(), "https://cdn.example.com/images-dev/user123/uploaded_test.png")
        finally:
            server.shutdown()
            server.server_close()

if __name__ == "__main__":
    unittest.main()
