import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "create_response.sh"


class DeepSeekV41FlashCreateResponseTests(unittest.TestCase):
    def run_script(self, *args: str, env=None):
        run_env = os.environ.copy() if env is None else env.copy()
        python_bin_dir = str(Path(sys.executable).parent)
        run_env["PATH"] = f"{python_bin_dir}{os.pathsep}{run_env.get('PATH', '')}"
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            text=True,
            capture_output=True,
            env=run_env,
            check=False,
        )

    def test_rejects_missing_input(self):
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required argument", result.stderr)

    def test_rejects_invalid_model(self):
        result = self.run_script("--input", "hello", "--model", "gpt-4.1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid model", result.stderr)

    def test_accepts_model_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
data_file=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    *) shift ;;
  esac
done
python3 - "$response" "$data_file" <<'PY'
import json, sys
with open(sys.argv[2], encoding="utf-8") as f:
    req = json.load(f)
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({"id": "resp_test", "model": req.get("model"), "output_text": "ok"}, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            python_bin_dir = str(Path(sys.executable).parent)
            env.update({
                "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                "FREVANA_TOKEN": "test-token",
            })

            # alias 1: deepseek-v4.1-flash
            res1 = self.run_script("--input", "hi", "--model", "deepseek-v4.1-flash", env=env)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            self.assertEqual(json.loads(res1.stdout)["model"], "deepseek/deepseek-v4.1-flash")

            # alias 2: deepseek-4.1-flash
            res2 = self.run_script("--input", "hi", "--model", "deepseek-4.1-flash", env=env)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            self.assertEqual(json.loads(res2.stdout)["model"], "deepseek/deepseek-v4.1-flash")

    def test_rejects_invalid_reasoning_effort(self):
        result = self.run_script("--input", "hello", "--reasoning-effort", "extreme")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --reasoning-effort", result.stderr)

    def test_rejects_invalid_temperature(self):
        result = self.run_script("--input", "hello", "--temperature", "3.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --temperature", result.stderr)

    def test_rejects_invalid_top_p(self):
        result = self.run_script("--input", "hello", "--top-p", "1.5")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --top-p", result.stderr)

    def test_rejects_invalid_service_tier(self):
        result = self.run_script("--input", "hello", "--service-tier", "hyperspeed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --service-tier", result.stderr)

    def test_payload_and_headers_reach_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
headers=()
data_file=''
target_url=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    -H) headers+=("$2"); shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    -X) shift 2 ;;
    http*|/*) target_url="$1"; shift ;;
    *) shift ;;
  esac
done

python3 - "$response" "$data_file" "$target_url" "${headers[@]}" <<'PY'
import json, sys
response_file = sys.argv[1]
data_file = sys.argv[2]
target_url = sys.argv[3]
headers = sys.argv[4:]

with open(data_file, encoding="utf-8") as f:
    req = json.load(f)

with open(response_file, "w", encoding="utf-8") as f:
    json.dump({
        "id": "resp_test123",
        "object": "response",
        "model": req.get("model"),
        "output_text": "Processed answer from deepseek flash",
        "output": [{
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Processed answer from deepseek flash"}]
        }],
        "captured_payload": req,
        "captured_headers": headers,
        "captured_url": target_url,
    }, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)

            env = os.environ.copy()
            python_bin_dir = str(Path(sys.executable).parent)
            env.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                    "FREVANA_TOKEN": "deepseek-token",
                    "FREVANA_API_KEY": "deepseek-api-key",
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-ds-1",
                }
            )

            result = self.run_script(
                "--input", "Write quicksort in Python",
                "--instructions", "Be concise and idiomatic.",
                "--reasoning-effort", "medium",
                "--temperature", "0.5",
                "--top-p", "0.9",
                "--max-output-tokens", "2048",
                "--service-tier", "ultrafast",
                "--previous-response-id", "resp_prev001",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            req = payload["captured_payload"]
            self.assertEqual(req["model"], "deepseek/deepseek-v4.1-flash")
            self.assertEqual(req["input"], "Write quicksort in Python")
            self.assertEqual(req["instructions"], "Be concise and idiomatic.")
            self.assertEqual(req["reasoning"], {"effort": "medium"})
            self.assertEqual(req["temperature"], 0.5)
            self.assertEqual(req["top_p"], 0.9)
            self.assertEqual(req["max_output_tokens"], 2048)
            self.assertEqual(req["service_tier"], "ultrafast")
            self.assertEqual(req["previous_response_id"], "resp_prev001")

            headers = payload["captured_headers"]
            self.assertIn("Authorization: Bearer deepseek-token", headers)
            self.assertIn("X-API-Key: deepseek-api-key", headers)
            self.assertIn("x-frevana-agent-app-instance-id: instance-ds-1", headers)

    def test_text_only_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    *) shift ;;
  esac
done
printf '{"id":"resp_abc","output_text":"Only this text should be visible."}' > "$response"
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            python_bin_dir = str(Path(sys.executable).parent)
            env.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                    "FREVANA_TOKEN": "test-token",
                }
            )

            result = self.run_script("--input", "hi", "--text-only", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "Only this text should be visible.")

    def test_agent_app_instance_id_env_and_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
headers=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    -H) headers+=("$2"); shift 2 ;;
    *) shift ;;
  esac
done
python3 - "$response" "${headers[@]}" <<'PY'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({
        "id": "resp_test",
        "output_text": "ok",
        "captured_headers": sys.argv[2:],
    }, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)

            # Test 1: FREVANA_AGENT_APP_INSTANCE_ID
            env1 = os.environ.copy()
            python_bin_dir = str(Path(sys.executable).parent)
            env1.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env1['PATH']}",
                    "FREVANA_TOKEN": "token-1",
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-env-1",
                }
            )
            res1 = self.run_script("--input", "test", env=env1)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            headers1 = json.loads(res1.stdout)["captured_headers"]
            self.assertIn("x-frevana-agent-app-instance-id: instance-env-1", headers1)

            # Test 2: CLI flag --agent-app-instance-id overrides env
            env2 = os.environ.copy()
            env2.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env2['PATH']}",
                    "FREVANA_TOKEN": "token-2",
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-env-old",
                }
            )
            res2 = self.run_script("--input", "test", "--agent-app-instance-id", "instance-flag-override", env=env2)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            headers2 = json.loads(res2.stdout)["captured_headers"]
            self.assertIn("x-frevana-agent-app-instance-id: instance-flag-override", headers2)

    def test_session_file_preserves_and_chains_context(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
data_file=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    *) shift ;;
  esac
done

python3 - "$response" "$data_file" <<'PY'
import json, sys
response_file, data_file = sys.argv[1], sys.argv[2]
with open(data_file, encoding="utf-8") as f:
    req = json.load(f)

turn = 2 if "previous_response_id" in req else 1
with open(response_file, "w", encoding="utf-8") as f:
    json.dump({
        "id": f"resp_turn_{turn}",
        "object": "response",
        "model": req.get("model"),
        "output_text": f"Response for turn {turn}",
        "captured_payload": req,
    }, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)

            session_file = temp_path / "session.json"
            python_bin_dir = str(Path(sys.executable).parent)
            env = os.environ.copy()
            env.update({
                "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                "FREVANA_TOKEN": "test-token",
            })

            # Turn 1
            res1 = self.run_script("--session-file", str(session_file), "--input", "Hello turn 1", env=env)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            data1 = json.loads(res1.stdout)
            self.assertEqual(data1["id"], "resp_turn_1")
            self.assertNotIn("previous_response_id", data1["captured_payload"])

            # Verify session file was created and contains resp_turn_1
            self.assertTrue(session_file.exists())
            with open(session_file, encoding="utf-8") as f:
                saved_session = json.load(f)
            self.assertEqual(saved_session["last_response_id"], "resp_turn_1")

            # Turn 2: run with the same session file
            res2 = self.run_script("--session-file", str(session_file), "--input", "Hello turn 2", env=env)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            data2 = json.loads(res2.stdout)
            self.assertEqual(data2["id"], "resp_turn_2")
            self.assertEqual(data2["captured_payload"]["previous_response_id"], "resp_turn_1")

            # Verify session file now points to resp_turn_2
            with open(session_file, encoding="utf-8") as f:
                saved_session2 = json.load(f)
            self.assertEqual(saved_session2["last_response_id"], "resp_turn_2")

    def test_auto_session_via_env_conversation_id(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
data_file=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    *) shift ;;
  esac
done

python3 - "$response" "$data_file" <<'PY'
import json, sys
response_file, data_file = sys.argv[1], sys.argv[2]
with open(data_file, encoding="utf-8") as f:
    req = json.load(f)

turn = 2 if "previous_response_id" in req else 1
with open(response_file, "w", encoding="utf-8") as f:
    json.dump({
        "id": f"resp_auto_{turn}",
        "object": "response",
        "model": req.get("model"),
        "output_text": f"Auto turn {turn}",
        "captured_payload": req,
    }, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)

            python_bin_dir = str(Path(sys.executable).parent)
            session_dir = temp_path / "sessions"
            env = os.environ.copy()
            env.update({
                "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                "FREVANA_TOKEN": "test-token",
                "CONVERSATION_ID": "chat-thread-deepseek-999",
                "FREVANA_SESSION_DIR": str(session_dir),
            })

            # Turn 1: without passing any session flags!
            res1 = self.run_script("--input", "My favorite editor is Vim", env=env)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            data1 = json.loads(res1.stdout)
            self.assertEqual(data1["id"], "resp_auto_1")
            self.assertNotIn("previous_response_id", data1["captured_payload"])

            # Turn 2: without passing any session flags!
            res2 = self.run_script("--input", "What was my favorite editor?", env=env)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            data2 = json.loads(res2.stdout)
            self.assertEqual(data2["id"], "resp_auto_2")
            # Automatically chained previous response ID!
            self.assertEqual(data2["captured_payload"]["previous_response_id"], "resp_auto_1")


if __name__ == "__main__":
    unittest.main()
