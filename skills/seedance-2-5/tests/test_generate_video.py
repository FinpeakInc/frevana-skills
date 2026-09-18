#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_video.sh"

class TestSeedance25Video(unittest.TestCase):
    def run_script(self, args, check=True):
        cmd = [str(SCRIPT_PATH)] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_help(self):
        res = self.run_script(["--help"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("bytedance/seedance-2.5", res.stdout)
        self.assertIn("720p", res.stdout)

    def test_dry_run_defaults(self):
        res = self.run_script(["--prompt", "Sci-fi spaceship journey", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["model"], "bytedance/seedance-2.5")
        self.assertEqual(payload["prompt"], "Sci-fi spaceship journey")
        self.assertEqual(payload["duration"], 5)
        self.assertEqual(payload["resolution"], "720p")
        self.assertEqual(payload["aspect_ratio"], "16:9")

    def test_invalid_resolution(self):
        res = self.run_script(["--prompt", "Test", "--resolution", "1080p", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid resolution", res.stderr)

    def test_extended_duration(self):
        res = self.run_script(["--prompt", "Test", "--duration", "25", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["duration"], 25)

if __name__ == "__main__":
    unittest.main()
