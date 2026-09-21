#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_video.sh"

class TestWan30Video(unittest.TestCase):
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
        self.assertIn("alibaba/wan-3.0", res.stdout)
        self.assertIn("480p", res.stdout)

    def test_dry_run_defaults(self):
        res = self.run_script(["--prompt", "An ink landscape", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["model"], "alibaba/wan-3.0")
        self.assertEqual(payload["prompt"], "An ink landscape")
        self.assertEqual(payload["duration"], 5)
        self.assertEqual(payload["resolution"], "720p")
        self.assertEqual(payload["aspectRatio"], "16:9")

    def test_dry_run_uses_api_request_casing(self):
        res = self.run_script([
            "--prompt", "Test",
            "--aspect-ratio", "9:16",
            "--first-frame", "https://example.com/first.png",
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
        ])
        self.assertNotIn("aspect_ratio", payload)
        self.assertNotIn("generate_audio", payload)
        self.assertNotIn("frame_images", payload)

    def test_last_frame_unsupported(self):
        res = self.run_script(["--prompt", "Test", "--last-frame", "last.jpg", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("does not support --last-frame", res.stderr)

    def test_invalid_duration(self):
        res = self.run_script(["--prompt", "Test", "--duration", "35", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid duration", res.stderr)

if __name__ == "__main__":
    unittest.main()
