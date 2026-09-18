#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_video.sh"

class TestSeedance20Video(unittest.TestCase):
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
        self.assertIn("bytedance/seedance-2.0", res.stdout)
        self.assertIn("4K", res.stdout)

    def test_dry_run_defaults(self):
        res = self.run_script(["--prompt", "A warrior meditating", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["model"], "bytedance/seedance-2.0")
        self.assertEqual(payload["prompt"], "A warrior meditating")
        self.assertEqual(payload["duration"], 5)
        self.assertEqual(payload["resolution"], "720p")
        self.assertEqual(payload["aspect_ratio"], "16:9")

    def test_invalid_duration(self):
        res = self.run_script(["--prompt", "Test", "--duration", "3", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid duration", res.stderr)

    def test_watermark_and_seed(self):
        res = self.run_script([
            "--prompt", "Test",
            "--seed", "999",
            "--no-watermark",
            "--dry-run"
        ])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["seed"], 999)
        self.assertEqual(
            payload["provider"]["options"]["byteplus"]["watermark"],
            False
        )

if __name__ == "__main__":
    unittest.main()
