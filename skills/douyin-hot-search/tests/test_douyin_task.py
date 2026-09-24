import json
import os
import shlex
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
HOT_SEARCH = SKILL_DIR.name == "douyin-hot-search"
SCRIPT = SKILL_DIR / "scripts" / "douyin_task.sh"
SCRIPT_FOR_BASH = (
    subprocess.check_output(["cygpath", "-u", str(SCRIPT)], text=True).strip()
    if os.name == "nt" else str(SCRIPT)
)
TASK_ID = "7af283fe-13aa-431d-a7cf-b58675701884"
RESULT = b'[{"source":"douyin","items":[1,2]}]'
CREATE_PATH = "/service/douyin/hot-search/tasks" if HOT_SEARCH else "/service/douyin/search/tasks"


class Handler(BaseHTTPRequestHandler):
    requests = []
    status = "READY"
    billing = "BILLED"
    redirect = False

    def send_json(self, status_code, body):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def record(self):
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        self.__class__.requests.append(
            (self.command, self.path, self.headers.get("Authorization"), body)
        )
        return body

    def do_POST(self):
        payload = json.loads(self.record())
        if self.__class__.redirect:
            self.send_response(302)
            self.send_header("Location", "/redirected")
            self.end_headers()
            return
        self.send_json(202, json.dumps({
            "task_id": TASK_ID,
            "client_task_id": payload["client_task_id"],
            "operation": "HOT_SEARCH" if HOT_SEARCH else "SEARCH",
            "status": "PENDING",
            "billing_status": "PENDING",
        }).encode())

    def do_GET(self):
        self.record()
        if self.path.endswith("/result"):
            if self.__class__.billing != "BILLED":
                self.send_json(409, b'{"message":"Task is not ready and billed"}')
            else:
                self.send_json(200, RESULT)
            return
        self.send_json(200, json.dumps({
            "task_id": TASK_ID,
            "status": self.__class__.status,
            "billing_status": self.__class__.billing,
            "error_message": "test failure" if self.__class__.status == "TRIGGER_UNKNOWN" else None,
        }).encode())

    def log_message(self, _format, *_args):
        pass


class DouyinSkillTest(unittest.TestCase):
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
        Handler.status = "READY"
        Handler.billing = "BILLED"
        Handler.redirect = False

    def run_script(self, *args):
        return subprocess.run(
            ["bash", SCRIPT_FOR_BASH, *args, "--api-base-url", self.base_url,
             "--token", "test-token"],
            cwd=SKILL_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    def create_options(self):
        if HOT_SEARCH:
            return ("--board", "hotspot", "--board", "social", "--max-results-per-board", "20")
        return ("--keyword", "露营", "--keyword", "户外", "--sort", "latest",
                "--publish-time", "one_week", "--duration", "under_1m",
                "--max-results-per-query", "100")

    def test_run_uses_correct_endpoint_token_and_preserves_result(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            result = self.run_script("run", "--client-task-id", "stable-1",
                                     *self.create_options(), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(result.stdout, RESULT)
            self.assertEqual(output.read_bytes(), RESULT)
        self.assertEqual(
            [(method, path) for method, path, _, _ in Handler.requests],
            [("POST", CREATE_PATH), ("GET", f"/service/douyin/tasks/{TASK_ID}"),
             ("GET", f"/service/douyin/tasks/{TASK_ID}/result")],
        )
        self.assertTrue(all(auth == "Bearer test-token" for _, _, auth, _ in Handler.requests))
        payload = json.loads(Handler.requests[0][3])
        self.assertEqual(payload["client_task_id"], "stable-1")
        if HOT_SEARCH:
            self.assertEqual(payload["boards"], ["hotspot", "social"])
            self.assertEqual(payload["max_results_per_board"], 20)
        else:
            self.assertEqual(payload["keywords"], ["露营", "户外"])
            self.assertEqual(payload["sort"], "latest")

    def test_create_and_status_separate_phases(self):
        result = self.run_script("create", *self.create_options())
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout)["task_id"], TASK_ID)
        result = self.run_script("status", "--task-id", TASK_ID)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout)["status"], "READY")

    def test_create_uses_server_default_board_when_omitted(self):
        result = self.run_script("create", "--client-task-id", "default-board")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        payload = json.loads(Handler.requests[0][3])
        self.assertEqual(payload, {"client_task_id": "default-board"})

    @unittest.skipIf(os.name == "nt", "POSIX-only Git Bash path simulation")
    def test_git_bash_path_conversion_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "Windows output" / "result.json"
            cygpath = root / "cygpath"
            cygpath.write_text(
                "#!/bin/sh\ncase \"$1\" in\n"
                "  -m) printf '%s\\n' \"$2\" ;;\n"
                f"  -u) printf '%s\\n' {shlex.quote(str(output))} ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            cygpath.chmod(0o755)
            env = os.environ.copy()
            env["OSTYPE"] = "msys"
            env["PATH"] = f"{root}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                ["bash", str(SCRIPT), "run", "--board", "hotspot",
                 "--output", r"C:\review output\result.json",
                 "--api-base-url", self.base_url, "--token", "test-token"],
                cwd=SKILL_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(result.stdout, RESULT)
            self.assertEqual(output.read_bytes(), RESULT)

    def test_terminal_failure_does_not_fetch_or_resubmit(self):
        Handler.status = "TRIGGER_UNKNOWN"
        Handler.billing = "NOT_CHARGED"
        result = self.run_script("run", *self.create_options())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TRIGGER_UNKNOWN", result.stderr.decode())
        self.assertEqual(len(Handler.requests), 2)

    def test_invalid_request_is_rejected_before_network(self):
        options = ("--max-results-per-board", "61") if HOT_SEARCH else (
            "--keyword", "test", "--max-results-per-query", "2001")
        result = self.run_script("create", *options)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(Handler.requests, [])

    def test_result_conflict_does_not_write_file(self):
        Handler.billing = "PENDING"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            result = self.run_script("result", "--task-id", TASK_ID, "--output", str(output))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("HTTP 409", result.stderr.decode())
            self.assertFalse(output.exists())

    def test_redirect_does_not_forward_token(self):
        Handler.redirect = True
        result = self.run_script("create", *self.create_options())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP 302", result.stderr.decode())
        self.assertEqual(len(Handler.requests), 1)


if __name__ == "__main__":
    unittest.main()
