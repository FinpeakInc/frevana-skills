#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_video.sh"

class TestVeo31Video(unittest.TestCase):
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
        self.assertIn("google/veo-3.1", res.stdout)
        self.assertIn("4K", res.stdout)

    def test_dry_run_defaults(self):
        res = self.run_script(["--prompt", "A cinematic sunrise", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["model"], "google/veo-3.1")
        self.assertEqual(payload["prompt"], "A cinematic sunrise")
        self.assertEqual(payload["duration"], 6)
        self.assertEqual(payload["resolution"], "720p")
        self.assertEqual(payload["aspect_ratio"], "16:9")

    def test_invalid_duration(self):
        res = self.run_script(["--prompt", "Test", "--duration", "5", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid duration", res.stderr)

    def test_seed_and_passthrough(self):
        res = self.run_script([
            "--prompt", "Test",
            "--seed", "12345",
            "--negative-prompt", "blurry",
            "--dry-run"
        ])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["seed"], 12345)
        self.assertEqual(
            payload["provider"]["options"]["google-vertex"]["parameters"]["negativePrompt"],
            "blurry"
        )

if __name__ == "__main__":
    unittest.main()
