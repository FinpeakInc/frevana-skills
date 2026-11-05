#!/usr/bin/env python3
"""CLI contract and job lifecycle tests. Every HTTP call uses a fake curl."""

import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_video.sh"
BASE = "https://ai-factory.frevana.com/openrouter/v1/videos"
JOB = "video_heygen_test"
URL = "https://cdn.example.com/video.mp4"

FAKE_CURL = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
log = Path(os.environ['MOCK_LOG'])
calls = json.loads(log.read_text()) if log.exists() else []
record = {'args': args}
if '--data-binary' in args:
    record['payload'] = json.loads(Path(args[args.index('--data-binary') + 1][1:]).read_text())
responses = json.loads(os.environ.get('MOCK_RESPONSES', '[]'))
index = len(calls)
calls.append(record)
log.write_text(json.dumps(calls))
if index >= len(responses):
    sys.stderr.write('Unexpected HTTP request in offline test')
    sys.exit(97)
response = responses[index]
body = response.get('body', {})
raw = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
Path(args[args.index('-o') + 1]).write_text(raw)
sys.stdout.write(str(response.get('http', 200)))
sys.exit(response.get('exit', 0))
'''

FAKE_DATE = r'''#!/usr/bin/env python3
import os
from pathlib import Path
path = Path(os.environ['MOCK_CLOCK'])
now = int(path.read_text()) if path.exists() else 1000
print(now)
path.write_text(str(now + 1))
'''


class HeyGenVideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name, source in (("curl", FAKE_CURL), ("date", FAKE_DATE), ("sleep", "#!/bin/sh\nexit 0\n")):
            path = self.bin / name
            path.write_text(source)
            path.chmod(0o755)
        self.log = self.root / "requests.json"
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("FREVANA_", "X_FREVANA_", "MOCK_"))}
        self.env.update(PATH=f"{self.bin}:{os.environ['PATH']}",
                        MOCK_LOG=str(self.log), MOCK_CLOCK=str(self.root / "clock"))

    def run_cli(self, *args, responses=(), auth=False, extra_env=None):
        self.log.write_text("[]")
        (self.root / "clock").unlink(missing_ok=True)
        env = dict(self.env, MOCK_RESPONSES=json.dumps(responses))
        if auth:
            env["FREVANA_TOKEN"] = "test-token"
        env.update(extra_env or {})
        return subprocess.run(["bash", str(SCRIPT), *args], env=env,
                              capture_output=True, text=True, timeout=15)

    def calls(self):
        return json.loads(self.log.read_text())

    def payload(self, *args):
        result = self.run_cli("--prompt", "A mug turns slowly, with quiet room sound.", *args, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        return json.loads(result.stdout)

    def reject(self, *args, message=None):
        result = self.run_cli("--prompt", "Test", *args, "--dry-run")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.calls(), [])
        if message:
            self.assertIn(message, result.stderr)

    @staticmethod
    def completed(url=URL, **extra):
        return {"body": {"id": JOB, "status": "completed", "delivery_status": "stored",
                         "unsignedUrls": [url], **extra}}

    def test_help(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("heygen/heygen-video-1", result.stdout)
        self.assertIn("--prompt-enhancement", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_defaults_use_frevana_casing_and_no_audio_toggle(self):
        body = self.payload()
        self.assertEqual(body["model"], "heygen/heygen-video-1")
        self.assertEqual((body["duration"], body["resolution"], body["aspectRatio"]), (5, "768p", "16:9"))
        self.assertEqual(body["provider"], {"options": {"heygen": {"prompt_enhancement": "quality"}}})
        for key in ("generateAudio", "generate_audio", "aspect_ratio", "mode", "watermark"):
            self.assertNotIn(key, body)

    def test_enhancement_is_a_string_under_heygen(self):
        for mode in ("turbo", "quality", "ultraquality", "disabled"):
            with self.subTest(mode=mode):
                body = self.payload("--prompt-enhancement", mode)
                self.assertEqual(body["provider"]["options"]["heygen"]["prompt_enhancement"], mode)

    def test_long_clips_require_compatible_enhancement_and_mode(self):
        for mode in ("turbo", "quality"):
            self.assertEqual(self.payload("--duration", "30", "--prompt-enhancement", mode)["duration"], 30)
        self.assertEqual(self.payload("--duration", "30", "--first-frame", "https://example.com/first.png")["duration"], 30)
        for args in (("--prompt-enhancement", "disabled"), ("--prompt-enhancement", "ultraquality"),
                     ("--reference-image", "https://example.com/ref.jpg"), ("--reference-video", "https://example.com/ref.mp4")):
            with self.subTest(args=args):
                self.reject("--duration", "16", *args, message="above 15 seconds")

    def test_invalid_scalar_parameters(self):
        for args in (("--duration", "4"), ("--duration", "31"), ("--duration", "auto"),
                     ("--duration", "5.5"), ("--resolution", "720p"), ("--resolution", "2k"),
                     ("--aspect-ratio", "adaptive"), ("--model", "heygen/avatar-iv"),
                     ("--prompt-enhancement", "true"), ("--size", "1280X720"),
                     ("--seed", "-1"), ("--seed", "4294967296"), ("--seed", "3.14"),
                     ("--poll-interval", "0"), ("--max-wait", "-1")):
            with self.subTest(args=args):
                self.reject(*args)

    def test_high_resolution_shape_constraints(self):
        for resolution in ("1080p", "2K"):
            self.assertEqual(self.payload("--resolution", resolution, "--aspect-ratio", "9:16")["resolution"], resolution)
            self.reject("--resolution", resolution, "--aspect-ratio", "1:1", message="requires aspect ratio")
            body = self.payload("--resolution", resolution, "--aspect-ratio", "1:1", "--first-frame", "https://example.com/a.png")
            self.assertIn("frameImages", body)

    def test_exact_size_replaces_semantic_dimensions(self):
        body = self.payload("--size", "1344x768", "--resolution", "720p", "--aspect-ratio", "3:2")
        self.assertEqual(body["size"], "1344x768")
        self.assertNotIn("resolution", body)
        self.assertNotIn("aspectRatio", body)

    def test_seed_boundaries(self):
        for value in ("0", "4294967295"):
            self.assertEqual(self.payload("--seed", value)["seed"], int(value))

    def test_first_frame_uses_camelcase(self):
        body = self.payload("--image", "https://example.com/first.png")
        self.assertEqual(body["frameImages"], [{"type": "image_url", "frameType": "first_frame",
                                              "imageUrl": {"url": "https://example.com/first.png"}}])

    def test_reference_types_and_order(self):
        body = self.payload("--reference-image", "https://example.com/1.png",
                            "--reference-video", "https://example.com/1.mp4",
                            "--reference-image", "https://example.com/2.png",
                            "--reference-audio", "https://example.com/1.wav", "--duration", "15")
        refs = body["inputReferences"]
        self.assertEqual([r["imageUrl"]["url"] for r in refs if r["type"] == "image_url"],
                         ["https://example.com/1.png", "https://example.com/2.png"])
        self.assertEqual([r["videoUrl"]["url"] for r in refs if r["type"] == "video_url"], ["https://example.com/1.mp4"])
        self.assertEqual([r["audioUrl"]["url"] for r in refs if r["type"] == "audio_url"], ["https://example.com/1.wav"])

    def test_reference_mode_validation(self):
        self.reject("--reference-audio", "https://example.com/a.wav", message="require at least one")
        for flag, maximum in (("--reference-image", 9), ("--reference-video", 3), ("--reference-audio", 3)):
            self.reject(*([flag, "https://example.com/ref"] * (maximum + 1)), message="At most")

    def test_openrouter_frame_precedence_preserves_both_fields(self):
        result = self.run_cli("--prompt", "Test", "--first-frame", "https://example.com/start.png",
                              "--reference-audio", "https://example.com/reference.wav",
                              "--duration", "30", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertIn("frameImages precedence", result.stderr)
        body = json.loads(result.stdout)
        self.assertEqual(body["duration"], 30)
        self.assertEqual(body["frameImages"][0]["frameType"], "first_frame")
        self.assertEqual(body["inputReferences"], [{"type": "audio_url", "audioUrl": {"url": "https://example.com/reference.wav"}}])

    def test_local_image_encoding_avoids_process_argument_size_limit(self):
        path = self.root / "large.png"
        data = b"\x89PNG\r\n\x1a\n" + b"x" * 300000
        path.write_bytes(data)
        body = self.payload("--first-frame", str(path))
        encoded = body["frameImages"][0]["imageUrl"]["url"]
        self.assertTrue(encoded.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(encoded.split(",", 1)[1]), data)
        path.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
        self.reject("--first-frame", str(path), message="at most 5 MiB")

    def test_combined_base64_body_limit_is_checked_before_http(self):
        path = self.root / "reference.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024 - 8))
        result = self.run_cli("--prompt", "Test", "--no-wait",
                              *(["--reference-image", str(path)] * 8), auth=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("50 MiB body limit", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_prompt_file_and_empty_prompt(self):
        path = self.root / "prompt.txt"
        path.write_text('陶杯缓慢转动。\nSoft room ambience.', encoding="utf-8")
        self.assertEqual(self.payload("--prompt-file", str(path))["prompt"], path.read_text())
        self.reject("--prompt", "   ", message="cannot be blank")
        path.write_text("a" * 32001)
        self.reject("--prompt-file", str(path), message="32000")

    def test_unsupported_controls(self):
        for args in (("--last-frame", "https://example.com/a.png"), ("--audio",), ("--no-audio",),
                     ("--watermark",), ("--voice-id", "voice")):
            with self.subTest(args=args):
                self.reject(*args)

    def test_missing_flag_value(self):
        result = self.run_cli("--prompt", "Test", "--duration")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a value", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_media_url_validation(self):
        self.reject("--reference-video", "file:///tmp/video.mp4")
        self.reject("--reference-video", "http://example.com/video.mp4", message="public HTTPS")
        self.reject("--first-frame", "https://name:password@example.com/a.png", message="public HTTPS")

    def test_status_and_wait_dry_runs_do_not_request_http(self):
        for command in ("status", "wait"):
            result = self.run_cli(command, "--job-id", JOB, "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"method": "GET", "url": f"{BASE}/{JOB}"})
            self.assertEqual(self.calls(), [])

    def test_authentication_required(self):
        result = self.run_cli("--prompt", "Test", "--no-wait")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Authentication required", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_submit_saves_raw_response_and_uses_token_precedence(self):
        raw = '{ "id": "video_heygen_test", "status": "pending", "unknown": 42 }'
        output = self.root / "job.json"
        result = self.run_cli("--prompt", "Test", "--no-wait", "--output", str(output), auth=True,
                              extra_env={"FREVANA_API_KEY": "other-test-key", "FREVANA_AGENT_APP_INSTANCE_ID": "app-test"},
                              responses=[{"body": raw, "http": 202}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, raw)
        self.assertEqual(output.read_text(), raw)
        call = self.calls()[0]
        self.assertIn(BASE, call["args"])
        self.assertIn("POST", call["args"])
        self.assertIn("Authorization: Bearer test-token", call["args"])
        self.assertIn("x-frevana-agent-app-instance-id: app-test", call["args"])
        self.assertNotIn("other-test-key", " ".join(call["args"]))
        self.assertEqual(call["payload"]["model"], "heygen/heygen-video-1")
        self.assertIn(JOB, result.stderr)

    def test_token_override_and_custom_origin(self):
        result = self.run_cli("status", "--job-id", JOB, "--token", "override-token",
                              "--api-base-url", "https://staging.example.com/", auth=True,
                              responses=[{"body": {"id": JOB, "status": "pending"}}])
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.calls()[0]["args"]
        self.assertIn("Authorization: Bearer override-token", args)
        self.assertNotIn("Authorization: Bearer test-token", args)
        self.assertFalse(any(arg.startswith("X-API-Key:") for arg in args))
        self.assertIn(f"https://staging.example.com/openrouter/v1/videos/{JOB}", args)

    def test_api_keys_are_rejected_without_http_or_secret_output(self):
        secret = "sk_test_offline.secret"
        for command in (("--prompt", "Test", "--no-wait"), ("status", "--job-id", JOB)):
            for args, env in ((("--api-key", secret), {}), ((), {"FREVANA_API_KEY": secret})):
                with self.subTest(command=command, args=args):
                    result = self.run_cli(*command, *args, extra_env=env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("JWT Bearer token", result.stderr)
                    self.assertNotIn(secret, result.stderr + result.stdout)
                    self.assertEqual(self.calls(), [])

    def test_submit_failures_never_retry(self):
        for response in ({"exit": 28, "http": "000", "body": ""}, {"http": 503, "body": {"error": "unavailable"}},
                         {"http": 202, "body": {"status": "pending"}}):
            with self.subTest(response=response):
                result = self.run_cli("--prompt", "Test", auth=True, responses=[response])
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(self.calls()), 1)

    def test_wait_handles_delivery_pending_then_stored(self):
        result = self.run_cli("wait", "--job-id", JOB, "--text-only", auth=True, responses=[
            {"body": {"id": JOB, "status": "completed", "delivery_status": "pending", "unsignedUrls": []}},
            self.completed(),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), URL)
        self.assertEqual(len(self.calls()), 2)
        self.assertTrue(all("GET" in call["args"] for call in self.calls()))

    def test_create_waits_once_then_preserves_final_raw_response(self):
        output = self.root / "job.json"
        final = '{"id":"video_heygen_test","status":"completed","unsigned_urls":["https://cdn.example.com/video.mp4"],"usage":{"cost":0.25}}'
        result = self.run_cli("--prompt", "Test", "--output", str(output), auth=True, responses=[
            {"body": {"id": JOB, "status": "pending"}, "http": 202}, {"body": final},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, final)
        self.assertEqual(output.read_text(), final)
        self.assertEqual([c["args"][c["args"].index("-X") + 1] for c in self.calls()], ["POST", "GET"])

    def test_wait_failures_stop_without_resubmission(self):
        for response in ({"body": {"status": "failed", "error": "failed test"}},
                         {"body": {"status": "completed", "delivery_status": "failed"}},
                         {"body": "not JSON"}, {"http": 401, "body": {"error": "expired"}}):
            with self.subTest(response=response):
                result = self.run_cli("wait", "--job-id", JOB, auth=True, responses=[response])
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(self.calls()), 1)
                self.assertIn("GET", self.calls()[0]["args"])

    def test_timeout_retains_job_id_and_latest_response(self):
        output = self.root / "job.json"
        result = self.run_cli("--prompt", "Test", "--max-wait", "3", "--output", str(output), auth=True,
                              responses=[{"body": {"id": JOB, "status": "pending"}, "http": 202},
                                         {"body": {"id": JOB, "status": "in_progress"}}])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Timed out", result.stderr)
        self.assertIn(JOB, result.stderr)
        self.assertEqual(json.loads(output.read_text())["status"], "in_progress")
        self.assertEqual([c["args"][c["args"].index("-X") + 1] for c in self.calls()], ["POST", "GET"])

    def test_create_text_only_still_saves_receipt(self):
        output = self.root / "job.json"
        result = self.run_cli("--prompt", "Test", "--no-wait", "--text-only", "--output", str(output), auth=True,
                              responses=[{"body": {"id": JOB, "status": "pending"}}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), JOB)
        self.assertEqual(json.loads(output.read_text())["id"], JOB)

    def test_external_download_never_receives_frevana_credentials(self):
        for url in (URL, "https://ai-factory.frevana.com.evil.example/videos/file.mp4", "https://openrouter.ai/api/v1/videos/file/content"):
            with self.subTest(url=url):
                output = self.root / "result.mp4"
                result = self.run_cli("wait", "--job-id", JOB, "--output", str(output), "--text-only", auth=True,
                                      extra_env={"FREVANA_AGENT_APP_INSTANCE_ID": "test-app"},
                                      responses=[self.completed(url), {"body": "test-mp4"}])
                self.assertEqual(result.returncode, 0, result.stderr)
                args = self.calls()[1]["args"]
                self.assertNotIn("-H", args)
                self.assertNotIn("test-token", " ".join(args))
                self.assertEqual(output.read_text(), "test-mp4")
                self.assertEqual(result.stdout.strip(), str(output))

    def test_same_origin_download_does_not_redirect_credentials(self):
        output = self.root / "result.mp4"
        result = self.run_cli("wait", "--job-id", JOB, "--output", str(output), auth=True,
                              responses=[self.completed(f"{BASE}/{JOB}/content"), {"body": "test-mp4"}])
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.calls()[1]["args"]
        self.assertIn("Authorization: Bearer test-token", args)
        self.assertNotIn("-L", args)

    def test_failed_download_preserves_existing_file(self):
        output = self.root / "result.mp4"
        output.write_text("previous video")
        result = self.run_cli("wait", "--job-id", JOB, "--output", str(output), auth=True,
                              responses=[self.completed(), {"exit": 22, "http": 403, "body": "denied"}])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Download failed", result.stderr)
        self.assertEqual(output.read_text(), "previous video")
        self.assertEqual(list(self.root.glob("*.part.*")), [])

    def test_invalid_output_and_job_options_are_rejected_before_submission(self):
        for args in (("create", "--prompt", "Test", "--job-id", JOB),
                     ("status", "--job-id", "../wrong"),
                     ("--prompt", "Test", "--no-wait", "--output", str(self.root / "a.mp4")),
                     ("--prompt", "Test", "--output", str(self.root))):
            with self.subTest(args=args):
                result = self.run_cli(*args, auth=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
