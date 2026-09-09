import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_image.sh"


class GenerateImageScriptTests(unittest.TestCase):
    def run_script(self, *args: str, env=None):
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_rejects_invalid_custom_size_before_auth(self):
        result = self.run_script("--prompt", "test", "--size", "1000x1000")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --size", result.stderr)

    def test_rejects_transparent_jpeg(self):
        result = self.run_script(
            "--prompt", "test", "--background", "transparent", "--output-format", "jpeg"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("require png or webp", result.stderr)

    def test_default_flare_and_new_generation_fields_reach_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
data=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --data) data="$2"; shift 2 ;;
    *) shift ;;
  esac
done
python3 - "${data#@}" "$response" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    request_payload = json.load(f)
with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump({
        "created": 1,
        "data": [{"image_url": "https://static.frevana.com/test.png"}],
        "credits_consumed": 1,
        "request_payload": request_payload,
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
                    "FREVANA_TOKEN": "test-token",
                }
            )
            result = self.run_script(
                "--prompt", "test", "--quality", "max", "--size", "2048x1152",
                "--moderation", "low", env=env
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout, f"expected JSON output; stderr={result.stderr!r}")
            payload = json.loads(result.stdout)["request_payload"]
            self.assertEqual(payload["model"], "gpt-image-2.5-flare")
            self.assertEqual(payload["quality"], "max")
            self.assertEqual(payload["size"], "2048x1152")
            self.assertEqual(payload["moderation"], "low")

    def test_explicit_sunburst_and_input_fidelity_reach_multipart_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            reference = temp_path / "reference.png"
            # Minimal valid 1x1 transparent PNG
            reference.write_bytes(
                b"\x89PNG\r\n\x1a\n"  # PNG signature
                b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
model=''
input_fidelity=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --form-string)
      case "$2" in
        model=*) model="${2#model=}" ;;
        input_fidelity=*) input_fidelity="${2#input_fidelity=}" ;;
      esac
      shift 2
      ;;
    *) shift ;;
  esac
done
printf '{"created":1,"data":[{"image_url":"https://static.frevana.com/edit.png"}],"credits_consumed":1,"request_model":"%s","request_input_fidelity":"%s"}' "$model" "$input_fidelity" > "$response"
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
            result = self.run_script(
                "--model", "gpt-image-2.5-sunburst", "--prompt", "precise edit",
                "--image", str(reference), "--input-fidelity", "high", env=env
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["request_model"], "gpt-image-2.5-sunburst")
            self.assertEqual(payload["request_input_fidelity"], "high")

    def test_agent_app_instance_header_is_sent_only_when_configured(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
agent_app_instance_header=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    -H)
      case "$2" in
        x-frevana-agent-app-instance-id:*) agent_app_instance_header="$2" ;;
      esac
      shift 2
      ;;
    *) shift ;;
  esac
done
printf '{"created":1,"data":[{"image_url":"https://static.frevana.com/test.png"}],"credits_consumed":1,"agent_app_instance_header":"%s"}' "$agent_app_instance_header" > "$response"
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
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-123",
                }
            )

            configured = self.run_script("--prompt", "test", env=env)
            self.assertEqual(configured.returncode, 0, configured.stderr)
            self.assertEqual(
                json.loads(configured.stdout)["agent_app_instance_header"],
                "x-frevana-agent-app-instance-id: instance-123",
            )

            env.pop("FREVANA_AGENT_APP_INSTANCE_ID")
            unset = self.run_script("--prompt", "test", env=env)
            self.assertEqual(unset.returncode, 0, unset.stderr)
            self.assertEqual(json.loads(unset.stdout)["agent_app_instance_header"], "")

    def test_rejects_empty_image_path(self):
        result = self.run_script("--prompt", "test", "--image", "")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not be empty", result.stderr)

    def test_rejects_fake_png_magic_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            fake_png = Path(temp) / "fake.png"
            fake_png.write_bytes(b"not-a-real-png")
            result = self.run_script("--prompt", "test", "--image", str(fake_png))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bad magic bytes", result.stderr)


if __name__ == "__main__":
    unittest.main()
