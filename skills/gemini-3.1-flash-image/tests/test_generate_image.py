import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_image.sh"

MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class GeminiFlashGenerateImageTests(unittest.TestCase):
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

    def test_rejects_missing_prompt(self):
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required argument", result.stderr)

    def test_rejects_invalid_model(self):
        result = self.run_script("--prompt", "test", "--model", "gemini-3-pro-image")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid model", result.stderr)

    def test_rejects_invalid_aspect_ratio(self):
        result = self.run_script("--prompt", "test", "--aspect-ratio", "16:10")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --aspect-ratio", result.stderr)

    def test_rejects_invalid_image_size(self):
        result = self.run_script("--prompt", "test", "--image-size", "8K")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --image-size", result.stderr)

    def test_rejects_invalid_candidate_count(self):
        result = self.run_script("--prompt", "test", "--candidate-count", "9")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --candidate-count", result.stderr)

    def test_rejects_invalid_temperature(self):
        result = self.run_script("--prompt", "test", "--temperature", "2.5")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --temperature", result.stderr)

    def test_rejects_invalid_top_p(self):
        result = self.run_script("--prompt", "test", "--top-p", "1.5")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --top-p", result.stderr)

    def test_rejects_invalid_top_k(self):
        result = self.run_script("--prompt", "test", "--top-k", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --top-k", result.stderr)

    def test_rejects_candidate_count_greater_than_one_on_image_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            img = Path(temp) / "ref.png"
            img.write_bytes(MINIMAL_PNG)
            result = self.run_script(
                "--prompt", "edit", "--image", str(img), "--candidate-count", "2"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Gemini image editing supports candidate_count=1 only", result.stderr)

    def test_rejects_sampling_params_on_image_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            img = Path(temp) / "ref.png"
            img.write_bytes(MINIMAL_PNG)

            res_temp = self.run_script(
                "--prompt", "edit", "--image", str(img), "--temperature", "1.0"
            )
            self.assertNotEqual(res_temp.returncode, 0)
            self.assertIn("--temperature is supported only for text-to-image generation", res_temp.stderr)

            res_top_p = self.run_script(
                "--prompt", "edit", "--image", str(img), "--top-p", "0.9"
            )
            self.assertNotEqual(res_top_p.returncode, 0)
            self.assertIn("--top-p is supported only for text-to-image generation", res_top_p.stderr)

            res_top_k = self.run_script(
                "--prompt", "edit", "--image", str(img), "--top-k", "40"
            )
            self.assertNotEqual(res_top_k.returncode, 0)
            self.assertIn("--top-k is supported only for text-to-image generation", res_top_k.stderr)

    def test_rejects_fake_png_magic_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            fake_png = Path(temp) / "fake.png"
            fake_png.write_bytes(b"not-a-real-png")
            result = self.run_script("--prompt", "test", "--image", str(fake_png))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bad magic bytes", result.stderr)

    def test_generation_fields_and_job_id_reach_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
url=''
form_fields=()
headers=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    -H) headers+=("$2"); shift 2 ;;
    --form-string) form_fields+=("$2"); shift 2 ;;
    http*|/*) url="$1"; shift ;;
    *) shift ;;
  esac
done

python3 - "$response" "$url" "${headers[@]}" "---FIELDS---" "${form_fields[@]}" <<'PY'
import json, sys
response_file = sys.argv[1]
url = sys.argv[2]
args = sys.argv[3:]
split_idx = args.index("---FIELDS---")
headers = args[:split_idx]
fields = args[split_idx + 1:]

field_dict = {}
for item in fields:
    if "=" in item:
        k, v = item.split("=", 1)
        field_dict[k] = v

with open(response_file, "w", encoding="utf-8") as f:
    json.dump({
        "generated_images": [{"image_url": "https://static.frevana.com/gemini-flash.png"}],
        "credits_consumed": 1,
        "captured_url": url,
        "captured_headers": headers,
        "captured_fields": field_dict,
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
                    "FREVANA_TOKEN": "test-bearer-token",
                    "FREVANA_API_KEY": "test-api-key",
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-abc",
                }
            )

            result = self.run_script(
                "--prompt", "A futuristic metropolis",
                "--job-id", "job-12345",
                "--aspect-ratio", "16:9",
                "--image-size", "2K",
                "--candidate-count", "2",
                "--system-instruction", "Photorealistic details",
                "--temperature", "0.8",
                "--top-p", "0.95",
                "--top-k", "40",
                "--seed", "12345",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("job_id=job-12345", payload["captured_url"])

            fields = payload["captured_fields"]
            self.assertEqual(fields["prompt"], "A futuristic metropolis")
            self.assertEqual(fields["model"], "gemini-3.1-flash-image")
            self.assertEqual(fields["aspect_ratio"], "16:9")
            self.assertEqual(fields["image_size"], "2K")
            self.assertEqual(fields["candidate_count"], "2")
            self.assertEqual(fields["system_instruction"], "Photorealistic details")
            self.assertEqual(fields["temperature"], "0.8")
            self.assertEqual(fields["top_p"], "0.95")
            self.assertEqual(fields["top_k"], "40")
            self.assertEqual(fields["seed"], "12345")

            headers = payload["captured_headers"]
            self.assertIn("X-API-Key: test-api-key", headers)
            self.assertIn("Authorization: Bearer test-bearer-token", headers)
            self.assertIn("x-frevana-agent-app-instance-id: instance-abc", headers)

    def test_image_multipart_editing_reaches_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            reference = temp_path / "ref.png"
            reference.write_bytes(MINIMAL_PNG)

            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
image_files=()
model=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --form-string)
      case "$2" in
        model=*) model="${2#model=}" ;;
      esac
      shift 2
      ;;
    -F)
      case "$2" in
        image=*) image_files+=("${2#image=}") ;;
      esac
      shift 2
      ;;
    *) shift ;;
  esac
done

python3 - "$response" "$model" "${image_files[@]}" <<'PY'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({
        "generated_images": [{"image_url": "https://static.frevana.com/gemini-edit.png"}],
        "credits_consumed": 1,
        "captured_model": sys.argv[2],
        "captured_images": sys.argv[3:],
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
                "--prompt", "edit this image",
                "--image", str(reference),
                "--candidate-count", "1",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["captured_model"], "gemini-3.1-flash-image")
            self.assertEqual(len(payload["captured_images"]), 1)
            self.assertIn("type=image/png", payload["captured_images"][0])

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
        "generated_images": [{"image_url": "https://static.frevana.com/test.png"}],
        "credits_consumed": 1,
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
            res1 = self.run_script("--prompt", "test", env=env1)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            headers1 = json.loads(res1.stdout)["captured_headers"]
            self.assertIn("x-frevana-agent-app-instance-id: instance-env-1", headers1)

            # Test 2: X_FREVANA_AGENT_APP_INSTANCE_ID
            env2 = os.environ.copy()
            env2.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env2['PATH']}",
                    "FREVANA_TOKEN": "token-2",
                    "X_FREVANA_AGENT_APP_INSTANCE_ID": "instance-env-2",
                }
            )
            res2 = self.run_script("--prompt", "test", env=env2)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            headers2 = json.loads(res2.stdout)["captured_headers"]
            self.assertIn("x-frevana-agent-app-instance-id: instance-env-2", headers2)

            # Test 3: CLI flag --agent-app-instance-id overrides env
            env3 = os.environ.copy()
            env3.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env3['PATH']}",
                    "FREVANA_TOKEN": "token-3",
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-env-old",
                }
            )
            res3 = self.run_script("--prompt", "test", "--agent-app-instance-id", "instance-flag-override", env=env3)
            self.assertEqual(res3.returncode, 0, res3.stderr)
            headers3 = json.loads(res3.stdout)["captured_headers"]
            self.assertIn("x-frevana-agent-app-instance-id: instance-flag-override", headers3)

            # Test 4: Unset does not send header
            env4 = os.environ.copy()
            env4.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env4['PATH']}",
                    "FREVANA_TOKEN": "token-4",
                }
            )
            env4.pop("FREVANA_AGENT_APP_INSTANCE_ID", None)
            env4.pop("X_FREVANA_AGENT_APP_INSTANCE_ID", None)
            res4 = self.run_script("--prompt", "test", env=env4)
            self.assertEqual(res4.returncode, 0, res4.stderr)
            headers4 = json.loads(res4.stdout)["captured_headers"]
            for h in headers4:
                self.assertFalse(h.startswith("x-frevana-agent-app-instance-id:"))


if __name__ == "__main__":
    unittest.main()
