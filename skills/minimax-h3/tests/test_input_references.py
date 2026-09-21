#!/usr/bin/env python3

import base64
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


class TestVideoInputReferences(unittest.TestCase):
    def run_skill(self, skill, args, check=True):
        script = REPO_ROOT / "skills" / skill / "scripts" / "generate_video.sh"
        return subprocess.run(
            [str(script), "--prompt", "Test"] + args + ["--dry-run"],
            capture_output=True,
            text=True,
            check=check,
        )

    def test_image_reference_support_matrix(self):
        supported = (
            ("minimax-h3", []),
            ("veo-3.1", []),
            ("wan-3.0", []),
            ("kling-v3.0-std", []),
            ("kling-v3.0-pro", []),
            ("seedance-2-0", []),
            ("seedance-2-0", ["--model", "bytedance/seedance-2.0-fast"]),
            ("seedance-2-0", ["--model", "bytedance/seedance-2.0-mini"]),
            ("seedance-2-5", []),
            ("seedance-2-5", ["--model", "bytedance/seedance-1-5-pro"]),
        )
        for skill, model_args in supported:
            with self.subTest(skill=skill, model_args=model_args):
                result = self.run_skill(
                    skill,
                    model_args + ["--reference-image", "https://example.com/reference.png"],
                )
                self.assertEqual(json.loads(result.stdout)["inputReferences"], [{
                    "type": "image_url",
                    "imageUrl": {"url": "https://example.com/reference.png"},
                }])

        unsupported = (
            ("minimax-h3-max", []),
            ("wan-3.0", ["--model", "alibaba/wan-3.0-prime"]),
        )
        for skill, model_args in unsupported:
            with self.subTest(skill=skill, model_args=model_args):
                result = self.run_skill(
                    skill,
                    model_args + ["--reference-image", "https://example.com/reference.png"],
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("does not support image input references", result.stderr)

    def test_seedance_2_generation_supports_all_reference_types(self):
        expected = [
            {"type": "image_url", "imageUrl": {"url": "https://example.com/reference.png"}},
            {"type": "audio_url", "audioUrl": {"url": "https://example.com/reference.mp3"}},
            {"type": "video_url", "videoUrl": {"url": "https://example.com/reference.mp4"}},
        ]
        for skill in ("seedance-2-0", "seedance-2-5"):
            with self.subTest(skill=skill):
                result = self.run_skill(skill, [
                    "--reference-image", "https://example.com/reference.png",
                    "--reference-audio", "https://example.com/reference.mp3",
                    "--reference-video", "https://example.com/reference.mp4",
                ])
                self.assertEqual(json.loads(result.stdout)["inputReferences"], expected)

    def test_non_seedance_2_models_reject_audio_and_video_references(self):
        cases = (
            ("minimax-h3", []),
            ("veo-3.1", []),
            ("wan-3.0", []),
            ("kling-v3.0-std", []),
            ("kling-v3.0-pro", []),
            ("seedance-2-5", ["--model", "bytedance/seedance-1-5-pro"]),
        )
        for skill, model_args in cases:
            for flag, kind in (("--reference-audio", "audio"), ("--reference-video", "video")):
                with self.subTest(skill=skill, flag=flag):
                    result = self.run_skill(
                        skill,
                        model_args + [flag, f"https://example.com/reference.{kind}"],
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(f"does not support {kind} input references", result.stderr)

    def test_allows_frame_images_combined_with_references(self):
        result = self.run_skill("seedance-2-5", [
            "--first-frame", "https://example.com/first.png",
            "--reference-image", "https://example.com/reference.png",
        ])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["frameImages"], [{
            "type": "image_url",
            "frameType": "first_frame",
            "imageUrl": {"url": "https://example.com/first.png"},
        }])
        self.assertEqual(payload["inputReferences"], [{
            "type": "image_url",
            "imageUrl": {"url": "https://example.com/reference.png"},
        }])

    def test_local_reference_image_is_encoded_as_data_uri(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "reference.png"
            image_bytes = b"not-a-real-png-but-valid-for-payload-testing"
            image_path.write_bytes(image_bytes)
            result = self.run_skill("minimax-h3", ["--reference-image", str(image_path)])
            url = json.loads(result.stdout)["inputReferences"][0]["imageUrl"]["url"]
            self.assertEqual(
                url,
                "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
            )


if __name__ == "__main__":
    unittest.main()
