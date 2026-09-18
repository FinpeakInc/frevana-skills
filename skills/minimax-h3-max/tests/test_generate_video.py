#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_video.sh"

class TestMinimaxH3MaxVideo(unittest.TestCase):
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
        self.assertIn("minimax/hailuo-3-max", res.stdout)
        self.assertIn("768p", res.stdout)
        self.assertIn("480p", res.stdout)

    def test_dry_run_defaults(self):
        res = self.run_script(["--prompt", "A panda in snow", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["model"], "minimax/hailuo-3-max")
        self.assertEqual(payload["prompt"], "A panda in snow")
        self.assertEqual(payload["duration"], 6)
        self.assertEqual(payload["resolution"], "768p")
        self.assertEqual(payload["aspect_ratio"], "16:9")

    def test_audio_unsupported(self):
        res = self.run_script(["--prompt", "Test", "--audio", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("does not support audio generation", res.stderr)

    def test_invalid_resolution(self):
        res = self.run_script(["--prompt", "Test", "--resolution", "2K", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid resolution", res.stderr)

if __name__ == "__main__":
    unittest.main()
