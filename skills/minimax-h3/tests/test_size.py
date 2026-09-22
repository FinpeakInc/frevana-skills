#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


class TestVideoSize(unittest.TestCase):
    def run_skill(self, skill, args, check=True):
        script = REPO_ROOT / "skills" / skill / "scripts" / "generate_video.sh"
        return subprocess.run(
            [str(script), "--prompt", "Test"] + args + ["--dry-run"],
            capture_output=True,
            text=True,
            check=check,
        )

    def test_size_replaces_resolution_and_aspect_ratio(self):
        cases = (
            ("minimax-h3", [], "1234x567"),
            ("minimax-h3-max", [], "1234x567"),
            ("veo-3.1", [], "1280x720"),
            ("wan-3.0", [], "1234x567"),
            ("kling-v3.0-std", [], "720x720"),
            ("kling-v3.0-pro", [], "720x1280"),
            ("seedance-2-0", [], "1920x1080"),
            ("seedance-2-5", [], "1112x834"),
        )
        for skill, model_args, size in cases:
            with self.subTest(skill=skill, model_args=model_args, size=size):
                result = self.run_skill(
                    skill,
                    model_args
                    + [
                        "--resolution",
                        "720p",
                        "--aspect-ratio",
                        "16:9",
                        "--size",
                        size,
                    ],
                )
                payload = json.loads(result.stdout)
                self.assertEqual(payload["size"], size)
                self.assertNotIn("resolution", payload)
                self.assertNotIn("aspectRatio", payload)

    def test_rejects_invalid_size_format(self):
        for value in ("1280X720", "1280:720", "0x720", "1280x0", "abc"):
            with self.subTest(value=value):
                result = self.run_skill(
                    "minimax-h3", ["--size", value], check=False
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid size", result.stderr)

    def test_all_models_accept_any_well_formed_size_for_api_validation(self):
        cases = (
            ("minimax-h3", []),
            ("minimax-h3-max", []),
            ("veo-3.1", []),
            ("veo-3.1", ["--model", "google/veo-3.1-lite"]),
            ("wan-3.0", []),
            ("wan-3.0", ["--model", "alibaba/wan-3.0-prime"]),
            ("kling-v3.0-std", []),
            ("kling-v3.0-pro", []),
            ("seedance-2-0", []),
            ("seedance-2-0", ["--model", "bytedance/seedance-2.0-fast"]),
            ("seedance-2-0", ["--model", "bytedance/seedance-2.0-mini"]),
            ("seedance-2-5", []),
            ("seedance-2-5", ["--model", "bytedance/seedance-1-5-pro"]),
        )
        for skill, model_args in cases:
            with self.subTest(skill=skill, model_args=model_args):
                result = self.run_skill(
                    skill, model_args + ["--size", "1234x567"]
                )
                self.assertEqual(json.loads(result.stdout)["size"], "1234x567")


if __name__ == "__main__":
    unittest.main()
