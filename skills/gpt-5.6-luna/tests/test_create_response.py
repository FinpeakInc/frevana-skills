import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "create_response.sh"


class Gpt56LunaCreateResponseTests(unittest.TestCase):
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
        result = self.run_script("--input", "hello", "--model", "gpt-5.6-sol")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid model", result.stderr)

    def test_rejects_invalid_reasoning_effort(self):
        result = self.run_script("--input", "hello", "--reasoning-effort", "invalid_effort")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --reasoning-effort", result.stderr)

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
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    -H) headers+=("$2"); shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    *) shift ;;
  esac
done

python3 - "$response" "$data_file" "${headers[@]}" <<'PY'
import json, sys
response_file = sys.argv[1]
data_file = sys.argv[2]
headers = sys.argv[3:]

with open(data_file, encoding="utf-8") as f:
    req = json.load(f)

with open(response_file, "w", encoding="utf-8") as f:
    json.dump({
        "id": "resp_luna_123",
        "object": "response",
        "model": req.get("model"),
        "output_text": "Processed fast response from luna",
        "captured_payload": req,
        "captured_headers": headers,
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
                    "FREVANA_TOKEN": "luna-token",
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-luna-1",
                }
            )

            result = self.run_script(
                "--input", "Summarize this article",
                "--instructions", "Keep it under 50 words.",
                "--temperature", "0.3",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            req = payload["captured_payload"]
            self.assertEqual(req["model"], "gpt-5.6-luna")
            self.assertEqual(req["input"], "Summarize this article")
            self.assertEqual(req["instructions"], "Keep it under 50 words.")
            self.assertEqual(req["temperature"], 0.3)

            headers = payload["captured_headers"]
            self.assertIn("Authorization: Bearer luna-token", headers)
            self.assertIn("x-frevana-agent-app-instance-id: instance-luna-1", headers)


if __name__ == "__main__":
    unittest.main()
