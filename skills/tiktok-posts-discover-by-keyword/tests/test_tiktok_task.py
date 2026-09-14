import json
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "tiktok_task.sh"
TASK_ID = "7af283fe-13aa-431d-a7cf-b58675701884"
RESULT = b'[{"ok":true,"source":"tiktok-posts-discover-by-keyword"}]'

class Handler(BaseHTTPRequestHandler):
    requests = []
    task_status = "READY"

    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        self.__class__.requests.append(
            (self.command, self.path, self.headers.get("Authorization"), body)
        )
        task = {
            "task_id": TASK_ID,
            "client_task_id": json.loads(body)["client_task_id"],
            "operation": "test",
            "snapshot_id": "s_test",
            "status": "TRIGGERED",
            "billing_status": "PENDING",
            "input_count": 1,
            "created_at": "2026-09-11T00:00:00.000Z",
            "ready_at": None,
        }
        self._send(202, json.dumps(task, separators=(",", ":")).encode())

    def do_GET(self):
        self.__class__.requests.append(
            (self.command, self.path, self.headers.get("Authorization"), b"")
        )
        if self.path.endswith("/result"):
            self._send(200, RESULT)
            return
        task = {
            "task_id": TASK_ID,
            "client_task_id": "client-fixed",
            "operation": "test",
            "snapshot_id": "s_test",
            "status": self.__class__.task_status,
            "billing_status": (
                "BILLED" if self.__class__.task_status == "READY" else "NOT_CHARGED"
            ),
            "input_count": 1,
            "created_at": "2026-09-11T00:00:00.000Z",
            "ready_at": "2026-09-11T00:00:01.000Z",
        }
        self._send(200, json.dumps(task, separators=(",", ":")).encode())

    def log_message(self, _format, *_args):
        pass

class TikTokSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        Handler.requests = []
        Handler.task_status = "READY"

    def run_script(self, *args):
        return subprocess.run(
            ["bash", str(SCRIPT), *args, "--api-base-url", self.base_url, "--token", "test-token"],
            cwd=SKILL_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_run_creates_polls_and_preserves_raw_result(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            result = self.run_script(
                "run",
                "--client-task-id",
                "client-fixed",
                "--input-json",
                '{"search_keyword":"#artist","num_of_posts":2,"country":"us"}',
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(result.stdout, RESULT)
            self.assertEqual(output.read_bytes(), RESULT)

        self.assertEqual(
            [(method, path) for method, path, _, _ in Handler.requests],
            [
                ("POST", "/service/tiktok/posts/discover-by-keyword"),
                ("GET", f"/service/tiktok/tasks/{TASK_ID}"),
                ("GET", f"/service/tiktok/tasks/{TASK_ID}/result"),
            ],
        )
        self.assertTrue(all(auth == "Bearer test-token" for _, _, auth, _ in Handler.requests))
        payload = json.loads(Handler.requests[0][3])
        self.assertEqual(payload["client_task_id"], "client-fixed")
        self.assertEqual(payload["input"], [{"search_keyword":"#artist","num_of_posts":2,"country":"US"}])

    def test_trigger_unknown_stops_without_fetching_or_resubmitting(self):
        Handler.task_status = "TRIGGER_UNKNOWN"
        result = self.run_script(
            "run",
            "--client-task-id",
            "client-unknown",
            "--input-json",
            '{"search_keyword":"#artist"}',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TRIGGER_UNKNOWN", result.stderr.decode())
        self.assertEqual(
            [(method, path) for method, path, _, _ in Handler.requests],
            [
                ("POST", "/service/tiktok/posts/discover-by-keyword"),
                ("GET", f"/service/tiktok/tasks/{TASK_ID}"),
            ],
        )

    def test_invalid_operation_input_is_rejected_before_network(self):
        result = self.run_script("create", "--input-json", '{"url":"https://www.tiktok.com/@wrong"}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("search_keyword", result.stderr.decode())
        self.assertEqual(Handler.requests, [])

if __name__ == "__main__":
    unittest.main()
