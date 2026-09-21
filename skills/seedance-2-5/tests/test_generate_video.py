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

    def test_invalid_resolution(self):
        res = self.run_script(["--prompt", "Test", "--resolution", "1080p", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid resolution", res.stderr)

    def test_extended_duration(self):
        res = self.run_script(["--prompt", "Test", "--duration", "25", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["duration"], 25)

    def test_seedance_15_pro_model_specific_capabilities(self):
        accepted = self.run_script([
            "--prompt", "Test", "--model", "bytedance/seedance-1-5-pro",
            "--duration", "12", "--resolution", "1080p",
            "--aspect-ratio", "9:21", "--dry-run",
        ])
        payload = json.loads(accepted.stdout)
        self.assertEqual(payload["duration"], 12)
        self.assertEqual(payload["resolution"], "1080p")
        self.assertEqual(payload["aspectRatio"], "9:21")

        rejected = self.run_script([
            "--prompt", "Test", "--model", "bytedance/seedance-1-5-pro",
            "--duration", "13", "--dry-run",
        ], check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("Invalid duration", rejected.stderr)

if __name__ == "__main__":
    unittest.main()
