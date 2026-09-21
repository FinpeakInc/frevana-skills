#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_video.sh"

class TestMinimaxH3Video(unittest.TestCase):
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
        self.assertIn("minimax/hailuo-3", res.stdout)
        self.assertIn("--duration", res.stdout)
        self.assertIn("--aspect-ratio", res.stdout)

    def test_dry_run_defaults(self):
        res = self.run_script(["--prompt", "A drone flying over autumn mountains", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["model"], "minimax/hailuo-3")
        self.assertEqual(payload["prompt"], "A drone flying over autumn mountains")
        self.assertEqual(payload["duration"], 6)
        self.assertEqual(payload["resolution"], "2K")
        self.assertEqual(payload["aspectRatio"], "16:9")

    def test_dry_run_uses_api_request_casing(self):
        res = self.run_script([
            "--prompt", "Test",
            "--aspect-ratio", "9:16",
            "--first-frame", "https://example.com/first.png",
            "--last-frame", "https://example.com/last.png",
            "--no-audio",
            "--dry-run",
        ])
        payload = json.loads(res.stdout)
        self.assertEqual(payload["aspectRatio"], "9:16")
        self.assertFalse(payload["generateAudio"])
        self.assertEqual(payload["frameImages"], [
            {
                "type": "image_url",
                "frameType": "first_frame",
                "imageUrl": {"url": "https://example.com/first.png"},
            },
            {
                "type": "image_url",
                "frameType": "last_frame",
                "imageUrl": {"url": "https://example.com/last.png"},
            },
        ])
        self.assertNotIn("aspect_ratio", payload)
        self.assertNotIn("generate_audio", payload)
        self.assertNotIn("frame_images", payload)

    def test_invalid_duration(self):
        res = self.run_script(["--prompt", "Test", "--duration", "4", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid duration", res.stderr)

    def test_invalid_resolution(self):
        res = self.run_script(["--prompt", "Test", "--resolution", "1080p", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid resolution", res.stderr)

    def test_seed_unsupported(self):
        res = self.run_script(["--prompt", "Test", "--seed", "42", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("does not support deterministic --seed", res.stderr)

    def test_watermark_passthrough(self):
        res = self.run_script(["--prompt", "Test", "--watermark", "--dry-run"])
        payload = json.loads(res.stdout)
        self.assertTrue(payload["provider"]["options"]["minimax"]["aigc_watermark"])

if __name__ == "__main__":
    unittest.main()
