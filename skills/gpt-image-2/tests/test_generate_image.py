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


if __name__ == "__main__":
    unittest.main()
