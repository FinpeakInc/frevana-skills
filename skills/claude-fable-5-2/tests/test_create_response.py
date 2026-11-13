import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "create_response.sh"


class ClaudeFable52CreateResponseTests(unittest.TestCase):
    def run_script(self, *args, env=None):
        run_env = (env or os.environ).copy()
        run_env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{run_env.get('PATH', '')}"
        return subprocess.run(["bash", str(SCRIPT), *args], text=True, capture_output=True, env=run_env, check=False)

    def test_local_validation(self):
        self.assertIn("Missing required", self.run_script().stderr)
        self.assertIn("Invalid model", self.run_script("--input", "x", "--model", "other").stderr)
        self.assertIn("Invalid --reasoning-effort", self.run_script("--input", "x", "--reasoning-effort", "extreme").stderr)
        self.assertIn("Invalid --max-output-tokens", self.run_script("--input", "x", "--max-output-tokens", "128001").stderr)
        self.assertIn("not supported", self.run_script("--input", "x", "--temperature").stderr)

        api_key_only = os.environ.copy()
        api_key_only.pop("FREVANA_TOKEN", None)
        api_key_only["FREVANA_API_KEY"] = "key-only"
        auth = self.run_script("--input", "x", env=api_key_only)
        self.assertNotEqual(auth.returncode, 0)
        self.assertIn("Bearer authentication required", auth.stderr)

    def make_env(self, root: Path, response=None, status="200"):
        response = response or {"id": "resp_fable", "status": "completed", "output_text": "answer"}
        fake_curl = root / "curl"
        fake_curl.write_text(f"""#!/usr/bin/env bash
set -euo pipefail
response=''; data_file=''; headers=(); url=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --data-binary) data_file="${{2#@}}"; shift 2 ;;
    -H) headers+=("$2"); shift 2 ;;
    http*) url="$1"; shift ;;
    *) shift ;;
  esac
done
python3 - "$response" "$data_file" "$url" "${{headers[@]}}" <<'PY'
import json, sys
body = {json.dumps(response)!r}
data = json.loads(body)
data['captured_payload'] = json.load(open(sys.argv[2], encoding='utf-8'))
data['captured_url'] = sys.argv[3]
data['captured_headers'] = sys.argv[4:]
json.dump(data, open(sys.argv[1], 'w', encoding='utf-8'))
PY
printf '{status}'
""", encoding="utf-8")
        fake_curl.chmod(0o755)
        env = os.environ.copy()
        env.update({"PATH": f"{root}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{env['PATH']}", "FREVANA_TOKEN": "token", "FREVANA_API_KEY": "key", "FREVANA_AGENT_APP_INSTANCE_ID": "app-1"})
        return env

    def test_payload_headers_text_and_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.make_env(root)
            session = root / "session.json"
            output = root / "response.json"
            tools = '[{"type":"function","name":"lookup","parameters":{"type":"object"}}]'
            result = self.run_script("--input", "analyze", "--model", "claude-fable-5-2", "--instructions", "be exact", "--reasoning-effort", "high", "--max-output-tokens", "32000", "--service-tier", "default", "--tools", tools, "--tool-choice", "auto", "--session-file", str(session), "--output", str(output), env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            req = data["captured_payload"]
            self.assertEqual(req["model"], "anthropic/claude-fable-5.2")
            self.assertEqual(req["input"], "analyze")
            self.assertEqual(req["instructions"], "be exact")
            self.assertEqual(req["reasoning"], {"effort": "high"})
            self.assertEqual(req["max_output_tokens"], 32000)
            self.assertFalse(req["stream"])
            self.assertEqual(req["tools"][0]["name"], "lookup")
            self.assertTrue(data["captured_url"].endswith("/openrouter/v1/responses"))
            self.assertIn("Authorization: Bearer token", data["captured_headers"])
            self.assertEqual(json.loads(session.read_text())["response_id"], "resp_fable")
            self.assertEqual(json.loads(output.read_text())["id"], "resp_fable")

            second = self.run_script("--input", "continue", "--session-file", str(session), "--text-only", env=env)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stdout.strip(), "answer")

    def test_raw_payload_fixed_model_and_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw.json"
            raw.write_text('{"input":"x","reasoning":{"effort":"max"}}')
            env = self.make_env(root, {"id": "resp_partial", "status": "incomplete", "output_text": "partial"})
            result = self.run_script("--raw-payload-file", str(raw), env=env)
            self.assertEqual(result.returncode, 2)
            data = json.loads(result.stdout)
            self.assertEqual(data["captured_payload"]["model"], "anthropic/claude-fable-5.2")
            self.assertFalse(data["captured_payload"]["stream"])

    def test_raw_payload_cannot_bypass_model_contract(self):
        invalid_payloads = (
            ({"input": "x", "temperature": 0.5}, "temperature is not supported"),
            ({"input": "x", "top_p": 0.9}, "top_p is not supported"),
            ({"input": "x", "service_tier": "fast"}, "only default service tier"),
            ({"input": "x", "max_output_tokens": 128001}, "max_output_tokens must be"),
            ({"input": "x", "tool_choice": "required"}, "tool_choice auto or none"),
        )
        with tempfile.TemporaryDirectory() as temp:
            raw = Path(temp) / "raw.json"
            for payload, expected in invalid_payloads:
                with self.subTest(payload=payload):
                    raw.write_text(json.dumps(payload), encoding="utf-8")
                    result = self.run_script("--raw-payload-file", str(raw))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected, result.stderr)

    def test_local_persistence_failure_preserves_paid_response_on_stdout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.make_env(root)
            blocker = root / "not-a-directory"
            blocker.write_text("x", encoding="utf-8")
            result = self.run_script(
                "--input", "hello",
                "--session-file", str(blocker / "session.json"),
                "--new-session",
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["id"], "resp_fable")
            self.assertIn("API response was emitted, but local persistence failed", result.stderr)

    def test_http_error_preserves_body(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.make_env(root, {"error": {"message": "bad request"}}, "400")
            result = self.run_script("--input", "x", env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bad request", result.stdout)
            self.assertIn("Do not retry automatically", result.stderr)


if __name__ == "__main__":
    unittest.main()
