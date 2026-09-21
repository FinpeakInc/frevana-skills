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
        res = self.run_script(["--prompt", "Test", "--duration", "3", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid duration", res.stderr)

    def test_fast_and_mini_reject_high_resolutions(self):
        for model in ("bytedance/seedance-2.0-fast", "bytedance/seedance-2.0-mini"):
            with self.subTest(model=model):
                res = self.run_script([
                    "--prompt", "Test", "--model", model,
                    "--resolution", "1080p", "--dry-run",
                ], check=False)
                self.assertNotEqual(res.returncode, 0)
                self.assertIn("Invalid resolution", res.stderr)

    def test_base_model_accepts_4k(self):
        res = self.run_script([
            "--prompt", "Test", "--model", "bytedance/seedance-2.0",
            "--resolution", "4K", "--dry-run",
        ])
        self.assertEqual(json.loads(res.stdout)["resolution"], "4K")

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
