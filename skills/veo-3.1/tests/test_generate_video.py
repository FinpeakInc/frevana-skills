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
        res = self.run_script(["--prompt", "Test", "--duration", "5", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid duration", res.stderr)

    def test_lite_rejects_4k_but_accepts_1080p(self):
        rejected = self.run_script([
            "--prompt", "Test", "--model", "google/veo-3.1-lite",
            "--resolution", "4K", "--dry-run",
        ], check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("Invalid resolution", rejected.stderr)

        accepted = self.run_script([
            "--prompt", "Test", "--model", "google/veo-3.1-lite",
            "--resolution", "1080p", "--dry-run",
        ])
        self.assertEqual(json.loads(accepted.stdout)["resolution"], "1080p")

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
