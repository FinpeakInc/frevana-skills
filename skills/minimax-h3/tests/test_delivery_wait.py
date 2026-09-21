#!/usr/bin/env python3

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
VIDEO_SKILLS = (
    "minimax-h3",
    "minimax-h3-max",
    "veo-3.1",
    "wan-3.0",
    "kling-v3.0-std",
    "kling-v3.0-pro",
    "seedance-2-0",
    "seedance-2-5",
)


class TestVideoDeliveryWait(unittest.TestCase):
    def test_all_scripts_wait_for_delivery_after_generation_completes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(textwrap.dedent("""\
                #!/usr/bin/env bash
                set -euo pipefail
                output=""
                while [[ $# -gt 0 ]]; do
                  if [[ "$1" == "-o" ]]; then output="$2"; shift 2; else shift; fi
                done
                count=0
                [[ -f "$FAKE_CURL_STATE" ]] && count="$(<"$FAKE_CURL_STATE")"
                count=$((count + 1))
                printf '%s' "$count" > "$FAKE_CURL_STATE"
                if [[ "$count" -eq 1 ]]; then
                  printf '%s' '{"status":"completed","delivery_status":"pending"}' > "$output"
                else
                  printf '%s' '{"status":"completed","delivery_status":"stored","unsignedUrls":["https://example.com/video.mp4"]}' > "$output"
                fi
                printf '200'
            """), encoding="utf-8")
            fake_curl.chmod(0o755)

            for skill in VIDEO_SKILLS:
                with self.subTest(skill=skill):
                    state = temp_path / f"{skill}.count"
                    env = os.environ.copy()
                    env["PATH"] = f"{temp_path}{os.pathsep}{env['PATH']}"
                    env["FAKE_CURL_STATE"] = str(state)
                    script = REPO_ROOT / "skills" / skill / "scripts" / "generate_video.sh"
                    result = subprocess.run(
                        [str(script), "wait", "--job-id", "test-job-12345", "--token", "test",
                         "--poll-interval", "0", "--max-wait", "5", "--text-only"],
                        capture_output=True,
                        text=True,
                        env=env,
                        check=True,
                    )
                    self.assertEqual(result.stdout.strip(), "https://example.com/video.mp4")
                    self.assertEqual(state.read_text(encoding="utf-8"), "2")


if __name__ == "__main__":
    unittest.main()
