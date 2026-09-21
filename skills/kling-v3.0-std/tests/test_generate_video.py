#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_video.sh"

class TestKlingStanderVideo(unittest.TestCase):
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
        self.assertIn("kwaivgi/kling-v3.0-std", res.stdout)
        self.assertIn("720p", res.stdout)

    def test_dry_run_defaults(self):
        res = self.run_script(["--prompt", "Cyberpunk car drift", "--dry-run"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["model"], "kwaivgi/kling-v3.0-std")
        self.assertEqual(payload["prompt"], "Cyberpunk car drift")
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

    def test_seed_unsupported(self):
        res = self.run_script(["--prompt", "Test", "--seed", "42", "--dry-run"], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("does not support deterministic --seed", res.stderr)

    def test_passthrough_negative_prompt(self):
        res = self.run_script([
            "--prompt", "Test",
            "--negative-prompt", "blurry",
            "--cfg-scale", "0.6",
            "--dry-run"
        ])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(
            payload["provider"]["options"]["kling"]["negative_prompt"],
            "blurry"
        )
        self.assertEqual(
            payload["provider"]["options"]["kling"]["cfg_scale"],
            0.6
        )

if __name__ == "__main__":
    unittest.main()
