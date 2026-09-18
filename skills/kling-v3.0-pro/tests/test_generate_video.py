#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_video.sh"

class TestKlingProVideo(unittest.TestCase):
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
        self.assertIn("kwaivgi/kling-v3.0-pro", res.stdout)
        self.assertIn("720p", res.stdout)

    def test_dry_run_defaults(self):
        res = self.run_script(["--prompt", "Cinematic astronaut visor", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["model"], "kwaivgi/kling-v3.0-pro")
        self.assertEqual(payload["prompt"], "Cinematic astronaut visor")
        self.assertEqual(payload["duration"], 5)
        self.assertEqual(payload["resolution"], "720p")
        self.assertEqual(payload["aspect_ratio"], "16:9")

    def test_seed_unsupported(self):
        res = self.run_script(["--prompt", "Test", "--seed", "42", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("does not support deterministic --seed", res.stderr)

    def test_passthrough(self):
        res = self.run_script([
            "--prompt", "Test",
            "--negative-prompt", "artifacts",
            "--cfg-scale", "0.7",
            "--dry-run"
        ])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(
            payload["provider"]["options"]["kling"]["negative_prompt"],
            "artifacts"
        )
        self.assertEqual(
            payload["provider"]["options"]["kling"]["cfg_scale"],
            0.7
        )

if __name__ == "__main__":
    unittest.main()
