import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_image.sh"
PNG = b"\x89PNG\r\n\x1a\n" + b"test"


class Seedream55GenerateImageTests(unittest.TestCase):
    def run_script(self, *args, env=None):
        run_env = (env or os.environ).copy()
        run_env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{run_env.get('PATH', '')}"
        return subprocess.run(["bash", str(SCRIPT), *args], text=True, capture_output=True, env=run_env, check=False)

    def test_rejects_missing_prompt_and_invalid_options(self):
        self.assertIn("Missing required", self.run_script().stderr)
        self.assertIn("Invalid model", self.run_script("--prompt", "x", "--model", "other").stderr)
        self.assertIn("Invalid --n", self.run_script("--prompt", "x", "--n", "2").stderr)
        self.assertIn("Invalid --resolution", self.run_script("--prompt", "x", "--resolution", "4K").stderr)
        self.assertIn("Invalid --aspect-ratio", self.run_script("--prompt", "x", "--aspect-ratio", "16:10").stderr)
        self.assertIn("Invalid --seed", self.run_script("--prompt", "x", "--seed", "1.5").stderr)

        api_key_only = os.environ.copy()
        api_key_only.pop("FREVANA_TOKEN", None)
        api_key_only["FREVANA_API_KEY"] = "key-only"
        auth = self.run_script("--prompt", "x", env=api_key_only)
        self.assertNotEqual(auth.returncode, 0)
        self.assertIn("Bearer authentication required", auth.stderr)

    def test_payload_headers_and_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "ref.png"
            image.write_bytes(PNG)
            fake_curl = root / "curl"
            fake_curl.write_text("""#!/usr/bin/env bash
set -euo pipefail
response=''; response_headers=''; data_file=''; headers=(); url=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    -D) response_headers="$2"; shift 2 ;;
    --data-binary) data_file="${2#@}"; shift 2 ;;
    -H) headers+=("$2"); shift 2 ;;
    http*) url="$1"; shift ;;
    *) shift ;;
  esac
done
printf 'HTTP/1.1 201 Created\r\nx-request-id: req_seedream_123\r\n\r\n' > "$response_headers"
python3 - "$response" "$data_file" "$url" "${headers[@]}" <<'PY'
import json, sys
req = json.load(open(sys.argv[2], encoding='utf-8'))
json.dump({'created': 1, 'credits_consumed': 0.4, 'data': [{'image_url': 'https://static.frevana.com/a.png', 'media_type': 'image/png'}], 'request': req, 'url': sys.argv[3], 'headers': sys.argv[4:]}, open(sys.argv[1], 'w', encoding='utf-8'))
PY
printf '201'
""", encoding="utf-8")
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            env.update({"PATH": f"{root}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{env['PATH']}", "FREVANA_TOKEN": "token", "FREVANA_API_KEY": "key", "FREVANA_AGENT_APP_INSTANCE_ID": "app-1"})
            output = root / "result.json"
            result = self.run_script("--prompt", "edit", "--model", "seedream-5-5", "--resolution", "1.5K", "--aspect-ratio", "4:3", "--seed", "-2", "--image", str(image), "--image-url", "https://example.com/ref.webp", "--output", str(output), env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            req = data["request"]
            self.assertEqual(req["model"], "bytedance-seed/seedream-5-5")
            self.assertEqual(req["n"], 1)
            self.assertFalse(req["stream"])
            self.assertEqual(req["resolution"], "1.5K")
            self.assertEqual(req["aspectRatio"], "4:3")
            self.assertEqual(req["seed"], -2)
            self.assertEqual(len(req["inputReferences"]), 2)
            self.assertTrue(req["inputReferences"][0]["imageUrl"]["url"].startswith("data:image/png;base64,"))
            self.assertEqual(req["inputReferences"][1]["imageUrl"]["url"], "https://example.com/ref.webp")
            self.assertTrue(data["url"].endswith("/openrouter/v1/images"))
            self.assertIn("Authorization: Bearer token", data["headers"])
            self.assertIn("X-API-Key: key", data["headers"])
            self.assertIn("x-frevana-agent-app-instance-id: app-1", data["headers"])
            self.assertEqual(json.loads(output.read_text())["data"][0]["image_url"], "https://static.frevana.com/a.png")
            self.assertIn("Frevana request ID: req_seedream_123", result.stderr)

    def test_rejects_encoded_request_over_server_body_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "large.png"
            with image.open("wb") as target:
                target.write(b"\x89PNG\r\n\x1a\n")
                target.truncate(38 * 1024 * 1024)
            result = self.run_script("--prompt", "edit", "--image", str(image))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds the server's 50MB JSON body limit", result.stderr)

    def test_http_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            counter = root / "count"
            fake_curl = root / "curl"
            fake_curl.write_text(f"""#!/usr/bin/env bash
set -euo pipefail
count=0; [[ -f '{counter}' ]] && count=$(< '{counter}'); printf '%s' $((count + 1)) > '{counter}'
response=''
while [[ $# -gt 0 ]]; do case "$1" in -o) response="$2"; shift 2 ;; *) shift ;; esac; done
printf '{{"error":{{"message":"upstream failed"}}}}' > "$response"
printf '502'
""", encoding="utf-8")
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            env.update({"PATH": f"{root}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{env['PATH']}", "FREVANA_TOKEN": "token"})
            result = self.run_script("--prompt", "x", env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(counter.read_text(), "1")
            self.assertIn("Do not retry automatically", result.stderr)


if __name__ == "__main__":
    unittest.main()
