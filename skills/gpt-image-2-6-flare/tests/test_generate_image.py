import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_image.sh"
MODEL = "gpt-image-2.6-flare"
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
RESPONSE = '{ "created": 1, "data": [{"image_url":"https://cdn.example/result.png","revised_prompt":null}], "credits_consumed": 1.25, "extra": {"preserve": true} }\n'

# Backend calls and downloads are intercepted. Selected regressions additionally
# run real curl with only file:// enabled to check its multipart parser offline.
FAKE_CURL = r'''#!/usr/bin/env python3
import json, os, re, subprocess, sys
from pathlib import Path

args = sys.argv[1:]
def option(name):
    return args[args.index(name) + 1] if name in args else None
record = {"args": args}
if "--data" in args:
    record["payload"] = json.loads(Path(option("--data")[1:]).read_text())
record["form"] = dict(args[i + 1].split("=", 1) for i, arg in enumerate(args) if arg == "--form-string")
record["files"] = [args[i + 1] for i, arg in enumerate(args) if arg == "-F"]
parse_result = None
if record["files"] and os.environ.get("TEST_REAL_CURL"):
    source = Path(os.environ["TEST_CURL_SOURCE"])
    source.unlink(missing_ok=True)
    command = [os.environ["TEST_REAL_CURL"], "--disable", "--silent", "--show-error",
               "--proto", "=file", "--max-time", "5", "--libcurl", str(source)]
    for field in record["files"]:
        command.extend(["-F", field])
    command.append(Path(os.environ["TEST_LOCAL_RESPONSE"]).as_uri())
    parse_result = subprocess.run(command, text=True, capture_output=True, timeout=10)
    record["file_parse_returncode"] = parse_result.returncode
    generated = source.read_text() if source.exists() else ""
    record["parsed_files"] = [json.loads(path) for path in re.findall(
        r'curl_mime_filedata\([^,]+,\s*("(?:[^"\\]|\\.)*")\);', generated)]
    record["parsed_file_contents"] = [Path(path).read_bytes().hex() for path in record["parsed_files"]]
with open(os.environ["TEST_CURL_LOG"], "a") as log:
    log.write(json.dumps(record) + "\n")
if parse_result is not None and parse_result.returncode:
    print(parse_result.stderr, file=sys.stderr)
    raise SystemExit(parse_result.returncode)
if "-D" in args:
    Path(option("-D")).write_text("HTTP/1.1 200 OK\r\nContent-Type: image/png\r\n\r\n")
    Path(option("-o")).write_bytes(Path(os.environ["TEST_REFERENCE"]).read_bytes())
    raise SystemExit(0)
if os.environ.get("TEST_TRANSPORT_ERROR"):
    raise SystemExit(28)
Path(option("-o")).write_text(os.environ["TEST_RESPONSE"])
print(os.environ.get("TEST_HTTP_CODE", "200"), end="")
'''


class GenerateImageScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "curl.jsonl"
        self.reference = self.root / "reference.png"
        self.reference.write_bytes(PNG)
        self.mask = self.root / "mask.png"
        self.mask.write_bytes(PNG)
        fake_curl = self.root / "curl"
        fake_curl.write_text(FAKE_CURL)
        fake_curl.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("FREVANA_")}
        self.env.update({
            "PATH": os.pathsep.join([str(self.root), str(Path(sys.executable).parent), self.env["PATH"]]),
            "FREVANA_TOKEN": "test-token",
            "TEST_CURL_LOG": str(self.log),
            "TEST_REFERENCE": str(self.reference),
            "TEST_RESPONSE": RESPONSE,
        })

    def run_script(self, *args, cwd=None):
        return subprocess.run(
            ["bash", str(SCRIPT), *args], input="", text=True,
            capture_output=True, env=self.env, cwd=cwd, check=False,
        )

    def enable_real_curl_form_check(self):
        real_curl = shutil.which("curl")
        self.assertIsNotNone(real_curl, "curl is required for offline multipart regression tests")
        response = self.root / "local-response.json"
        response.write_text(RESPONSE)
        self.env.update({
            "TEST_REAL_CURL": real_curl,
            "TEST_CURL_SOURCE": str(self.root / "request.c"),
            "TEST_LOCAL_RESPONSE": str(response),
        })

    def requests(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def assert_rejected_without_request(self, args, error):
        before = len(self.requests())
        result = self.run_script("--prompt", "test", *args)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(error, result.stderr)
        self.assertEqual(len(self.requests()), before)

    def test_fixed_model_route_defaults_and_raw_response(self):
        result = self.run_script("--contents", "画一座灯塔")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, RESPONSE)
        request, = self.requests()
        self.assertEqual(request["payload"], {"model": MODEL, "prompt": "画一座灯塔"})
        self.assertIn("https://ai-factory.frevana.com/openai/image/generate", request["args"])
        self.assertIn("Authorization: Bearer test-token", request["args"])
        self.assertEqual(request["files"], [])

    def test_generation_fields_and_output_file(self):
        target = self.root / "out" / "result.json"
        result = self.run_script(
            "--prompt", "product", "--n", "2", "--size", "2048x1152",
            "--quality", "max", "--complexity", "medium", "--background", "opaque",
            "--output-format", "webp", "--output-compression", "80", "--moderation", "low",
            "--output", str(target),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests()[0]["payload"], {
            "model": MODEL, "prompt": "product", "n": 2, "size": "2048x1152", "quality": "max",
            "complexity": "medium", "background": "opaque", "output_format": "webp",
            "output_compression": 80, "moderation": "low",
        })
        self.assertEqual(target.read_bytes(), RESPONSE.encode())
        self.assertEqual(result.stdout, RESPONSE)

    def test_all_quality_and_complexity_values(self):
        for quality in ("auto", "low", "medium", "high", "xhigh", "max"):
            with self.subTest(quality=quality):
                result = self.run_script("--prompt", "test", "--quality", quality)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.requests()[-1]["payload"]["quality"], quality)
        for complexity in ("low", "medium", "high"):
            with self.subTest(complexity=complexity):
                result = self.run_script("--prompt", "test", "--complexity", complexity)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.requests()[-1]["payload"]["complexity"], complexity)

    def test_static_edit_fields_and_literal_prompt_reach_multipart_backend(self):
        prompt = '@do-not-open;type=text/plain\n保留产品细节'
        result = self.run_script(
            "--prompt", prompt, "--image", str(self.reference), "--mask", str(self.mask),
            "--input-fidelity", "high", "--complexity", "low", "--quality", "xhigh",
            "--background", "transparent", "--size", "1024x1024", "--n", "1",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        request, = self.requests()
        self.assertNotIn("payload", request)
        self.assertEqual(request["form"], {
            "model": MODEL, "prompt": prompt, "input_fidelity": "high", "complexity": "low",
            "quality": "xhigh", "background": "transparent", "output_format": "png",
            "size": "1024x1024", "n": "1",
        })
        self.assertEqual(request["files"], [
            f'image=@"{self.reference}";type=image/png', f'mask=@"{self.mask}";type=image/png',
        ])

    def test_reference_urls_and_recursive_directories(self):
        nested = self.root / "refs" / "nested"
        nested.mkdir(parents=True)
        (nested / "local.png").write_bytes(PNG)
        (nested / "ignore.txt").write_text("ignore")
        result = self.run_script(
            "--prompt", "edit", "--image-url", "https://example.invalid/ref.png",
            "--image-dir", str(nested.parent),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        download, request = self.requests()
        self.assertIn("-D", download["args"])
        self.assertNotIn("-H", download["args"])
        self.assertEqual(len(request["files"]), 2)
        self.assertEqual(request["form"]["model"], MODEL)

    def test_special_reference_and_mask_paths_are_read_exactly_by_real_curl(self):
        self.enable_real_curl_form_check()
        # Without curl-level quoting, a,b.png is parsed as these two other files.
        (self.root / "a").write_bytes(b"unrequested file")
        (self.root / "mask-a").write_bytes(b"unrequested mask")
        (self.root / "b.png").write_bytes(PNG + b"unrequested reference")
        for name in ("a,b.png", "product;front.png", 'product"front.png', r"product\front.png"):
            with self.subTest(name=name):
                reference = self.root / name
                mask = self.root / ("mask-" + name)
                reference.write_bytes(PNG + b"requested reference")
                mask.write_bytes(PNG + b"requested mask")
                result = self.run_script(
                    "--prompt", "edit", "--image", str(reference), "--mask", str(mask), cwd=self.root,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                request = self.requests()[-1]
                self.assertEqual(request["file_parse_returncode"], 0)
                self.assertEqual(request["parsed_files"], [str(reference), str(mask)])
                self.assertEqual(request["parsed_file_contents"], [reference.read_bytes().hex(), mask.read_bytes().hex()])

    def test_url_first_reference_remains_mask_target_among_mixed_inputs(self):
        self.enable_real_curl_form_check()
        overlay = self.root / "overlay.png"
        overlay.write_bytes(PNG + b"overlay")
        last = self.root / "last.png"
        last.write_bytes(PNG + b"last")
        directory = self.root / 'refs, "details"'
        directory.mkdir()
        for name in ("b.png", "a.png"):
            (directory / name).write_bytes(PNG + name.encode())
        result = self.run_script(
            "--prompt", "edit first URL image", "--image-url", "https://example.invalid/base.png",
            "--image", str(overlay), "--image-dir", str(directory),
            "--image-url", "https://example.invalid/detail.png", "--image", str(last),
            "--mask", str(self.mask),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        request = self.requests()[-1]
        self.assertEqual(request["file_parse_returncode"], 0)
        self.assertEqual([Path(path).name for path in request["parsed_files"]], [
            "download-0.png", "overlay.png", "a.png", "b.png", "download-1.png", "last.png", "mask.png",
        ])
        self.assertEqual(request["parsed_file_contents"][0], self.reference.read_bytes().hex())

    def test_directory_first_expands_in_place_before_later_references(self):
        self.enable_real_curl_form_check()
        directory = self.root / "base"
        (directory / "nested").mkdir(parents=True)
        first = directory / "a.png"
        first.write_bytes(PNG + b"masked base")
        (directory / "nested" / "b.png").write_bytes(PNG + b"detail")
        result = self.run_script(
            "--prompt", "edit first directory image", "--image-dir", str(directory),
            "--image-url", "https://example.invalid/reference.png", "--image", str(self.reference),
            "--mask", str(self.mask),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        request = self.requests()[-1]
        self.assertEqual([Path(path).name for path in request["parsed_files"]], [
            "a.png", "b.png", "download-0.png", "reference.png", "mask.png",
        ])
        self.assertEqual(request["parsed_files"][0], str(first))
        self.assertEqual(request["parsed_file_contents"][0], first.read_bytes().hex())

    def test_auth_override_base_url_and_optional_attribution(self):
        self.env["FREVANA_API_BASE_URL"] = "http://127.0.0.1:3001///"
        self.env["FREVANA_AGENT_APP_INSTANCE_ID"] = "instance-123"
        result = self.run_script("--prompt", "test", "--token", "override-token")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.requests()[-1]["args"]
        self.assertIn("http://127.0.0.1:3001/openai/image/generate", args)
        self.assertIn("Authorization: Bearer override-token", args)
        self.assertIn("x-frevana-agent-app-instance-id: instance-123", args)
        self.assertNotIn("Authorization: Bearer test-token", args)
        self.env.pop("FREVANA_AGENT_APP_INSTANCE_ID")
        result = self.run_script("--prompt", "test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(a.startswith("x-frevana-agent-app-instance-id:") for a in self.requests()[-1]["args"]))

    def test_missing_token_fails_before_downloading_references(self):
        self.env.pop("FREVANA_TOKEN")
        self.env["FREVANA_API_KEY"] = "not-a-token-fallback"
        self.assert_rejected_without_request(
            ["--image-url", "https://example.invalid/ref.png"], "FREVANA_TOKEN is not set",
        )

    def test_fixed_routing_rejects_model_and_provider_overrides(self):
        for args in (
            ["--model", "gpt-image-2.5-flare"], ["--model", "gpt-image-2.6-sunburst"],
            [f"--model={MODEL}"], ["--provider", "gemini"], ["--provider=openai"],
        ):
            with self.subTest(args=args):
                self.assert_rejected_without_request(args, "This skill fixes")

    def test_missing_prompt_empty_values_and_unsupported_options(self):
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required", result.stderr)
        for args in (["--complexity"], ["--frame-count", ""], ["--image", ""], ["--prompt", ""]):
            with self.subTest(args=args):
                self.assert_rejected_without_request(args, "Missing or empty")
        for option in ("--stream", "--partial-images", "--job-id", "--markup"):
            self.assert_rejected_without_request([option, "1"], "Unknown argument")
        self.assert_rejected_without_request(["--output-format", "svg"], "Invalid --output-format")

    def test_invalid_static_options_fail_without_request(self):
        for args, error in (
            (["--quality", "ultra"], "Invalid --quality"),
            (["--complexity", "auto"], "Invalid --complexity"),
            (["--background", "white"], "Invalid --background"),
            (["--moderation", "off"], "Invalid --moderation"),
            (["--input-fidelity", "max"], "Invalid --input-fidelity"),
            (["--input-fidelity", "high"], "requires at least one reference"),
            (["--moderation", "low", "--image", str(self.reference)], "only for generation"),
            (["--mask", str(self.mask)], "requires at least one reference"),
            (["--background", "transparent", "--output-format", "jpeg"], "require png or webp"),
            (["--output-compression", "50"], "requires --output-format jpeg or webp"),
        ):
            with self.subTest(args=args):
                self.assert_rejected_without_request(args, error)

    def test_invalid_integer_fields_and_sizes(self):
        for option, values in (
            ("--n", ("0", "11", "1.5", "-1", "18446744073709551617")),
            ("--output-compression", ("0", "101", "2.5")),
            ("--frame-count", ("1", "17", "2.5", "-1")),
            ("--frame-duration-ms", ("19", "2001", "20.5", "bad")),
            ("--size", ("1000x1000", "0x16", "-16x32", "1024X1024", "1600x16", "9007199254740992x16")),
        ):
            for value in values:
                with self.subTest(option=option, value=value):
                    self.assert_rejected_without_request([option, value], f"Invalid {option}")

    def test_gif_fields_and_result_are_preserved(self):
        response = RESPONSE.replace("result.png", "animation.gif").replace('"created": 1', '"created": 1, "output_format": "gif"')
        self.env["TEST_RESPONSE"] = response
        result = self.run_script(
            "--prompt", "loop", "--output-format", "gif", "--frame-count", "16",
            "--frame-duration-ms", "2000", "--size", "auto", "--n", "2",
            "--quality", "medium", "--complexity", "low", "--moderation", "auto",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, response)
        self.assertEqual(self.requests()[0]["payload"], {
            "model": MODEL, "prompt": "loop", "output_format": "gif", "frame_count": 16,
            "frame_duration_ms": 2000, "size": "auto", "n": 2, "quality": "medium",
            "complexity": "low", "moderation": "auto",
        })

    def test_gif_defaults_are_left_to_server_and_small_frames_are_allowed(self):
        result = self.run_script("--prompt", "loop", "--output-format", "gif", "--size", "256x256")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests()[0]["payload"], {
            "model": MODEL, "prompt": "loop", "output_format": "gif", "size": "256x256",
        })

    def test_gif_omitted_size_selects_auto_without_inventing_other_options(self):
        result = self.run_script("--prompt", "loop", "--output-format", "gif")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests()[0]["payload"], {
            "model": MODEL, "prompt": "loop", "output_format": "gif", "size": "auto",
        })

    def test_gif_sheet_rejections_preserve_request_and_error_without_retry(self):
        errors = {
            16: "Invalid size '4096x4096'. The longest edge must be less than or equal to 3840.",
            9: "Invalid size '3072x3072'. Requested resolution exceeds the current pixel budget.",
            4: "Invalid size '4096x2048'. The longest edge must be less than or equal to 3840.",
        }
        for frames, detail in errors.items():
            with self.subTest(frames=frames):
                error = json.dumps({"code": "invalid_value", "message":
                    f"400 No supported sheet fits {frames} GIF frames at size '1024x1024'. {detail}"})
                self.env.update(TEST_HTTP_CODE="400", TEST_RESPONSE=error)
                before = len(self.requests())
                result = self.run_script(
                    "--prompt", "loop", "--output-format", "gif", "--size", "1024x1024",
                    "--frame-count", str(frames), "--frame-duration-ms", "150", "--quality", "max",
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn(error, result.stderr)
                self.assertIn("--size auto", result.stderr)
                self.assertIn("Do not guess progressively smaller frame counts", result.stderr)
                self.assertEqual(len(self.requests()), before + 1)
                self.assertEqual(self.requests()[-1]["payload"], {
                    "model": MODEL, "prompt": "loop", "output_format": "gif", "size": "1024x1024",
                    "frame_count": frames, "frame_duration_ms": 150, "quality": "max",
                })

    def test_gif_auto_sheet_error_does_not_recommend_repeating_auto(self):
        self.env.update(TEST_HTTP_CODE="400", TEST_RESPONSE=json.dumps({
            "code": "invalid_value", "message": "No supported sheet fits 9 GIF frames at size 'auto'.",
        }))
        result = self.run_script("--prompt", "loop", "--output-format", "gif")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("size=auto was also rejected", result.stderr)
        self.assertNotIn("use --size auto", result.stderr)
        self.assertEqual(len(self.requests()), 1)

    def test_gif_lower_bounds_and_decimal_leading_zero_values(self):
        result = self.run_script(
            "--prompt", "loop", "--output-format", "gif", "--frame-count", "02",
            "--frame-duration-ms", "020", "--n", "09",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.requests()[0]["payload"]
        self.assertEqual((payload["frame_count"], payload["frame_duration_ms"], payload["n"]), (2, 20, 9))

    def test_gif_rejects_reference_inputs_before_download_or_file_access(self):
        for option, value in (
            ("--image", "missing.png"), ("--image-url", "https://example.invalid/ref.png"),
            ("--image-dir", "missing-directory"), ("--mask", "missing-mask.png"),
            ("--input-fidelity", "high"),
        ):
            with self.subTest(option=option):
                self.assert_rejected_without_request(["--output-format", "gif", option, value], "text-only")

    def test_gif_rejects_transparency_and_compression(self):
        self.assert_rejected_without_request(
            ["--output-format", "gif", "--background", "transparent"], "require png or webp",
        )
        self.assert_rejected_without_request(
            ["--output-format", "gif", "--output-compression", "50"], "requires --output-format jpeg or webp",
        )

    def test_frame_fields_rejected_for_every_static_format_or_omitted_format(self):
        for format_args in ([], ["--output-format", "png"], ["--output-format", "jpeg"], ["--output-format", "webp"]):
            for option, value in (("--frame-count", "9"), ("--frame-duration-ms", "200")):
                with self.subTest(format_args=format_args, option=option):
                    self.assert_rejected_without_request([*format_args, option, value], "require --output-format gif")

    def test_gif_invalid_dimensions_fail_without_request(self):
        for size in ("0x16", "17x32", "-16x32", "9007199254740992x16"):
            self.assert_rejected_without_request(["--output-format", "gif", "--size", size], "Invalid --size")

    def test_invalid_reference_content_formats_and_masks(self):
        self.reference.write_bytes(b"not-a-real-png")
        self.assert_rejected_without_request(["--image", str(self.reference)], "bad magic bytes")
        self.reference.write_bytes(PNG)
        disguised = self.root / "wrong.jpg"
        disguised.write_bytes(PNG)
        self.assert_rejected_without_request(["--image", str(disguised)], "bad magic bytes")
        gif = self.root / "input.gif"
        gif.write_bytes(b"GIF89a")
        self.assert_rejected_without_request(["--image", str(gif)], "Unsupported reference image")
        self.mask.write_bytes(b"not-png")
        self.assert_rejected_without_request(["--image", str(self.reference), "--mask", str(self.mask)], "PNG image data")

    def test_reference_count_and_size_limits(self):
        self.assert_rejected_without_request(["--image", str(self.reference)] * 17, "At most 16")
        with self.reference.open("r+b") as image:
            image.truncate(50 * 1024 * 1024)
        self.assert_rejected_without_request(["--image", str(self.reference)], "less than 50MB")
        self.reference.write_bytes(PNG)
        with self.mask.open("r+b") as mask:
            mask.truncate(4 * 1024 * 1024)
        self.assert_rejected_without_request(["--image", str(self.reference), "--mask", str(self.mask)], "less than 4MB")

    def test_http_error_is_reported_without_retry(self):
        self.env.update(TEST_HTTP_CODE="400", TEST_RESPONSE='{"message":"GIF preview unavailable"}')
        result = self.run_script("--prompt", "loop", "--output-format", "gif")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP 400", result.stderr)
        self.assertIn("GIF preview unavailable", result.stderr)
        self.assertNotIn("--size auto", result.stderr)
        self.assertEqual(len(self.requests()), 1)
        self.assertEqual(result.stdout, "")

    def test_gif_guidance_is_not_added_to_unrelated_failures(self):
        for args, status, body in (
            (["--output-format", "png"], "400", {"code": "invalid_value", "message": "No supported sheet fits"}),
            (["--output-format", "gif"], "400", {"code": "moderation_blocked", "message": "Request blocked"}),
            (["--output-format", "gif"], "500", {"code": "invalid_value", "message": "No supported sheet fits"}),
            (["--output-format", "gif"], "400", ["No supported sheet fits"]),
        ):
            with self.subTest(args=args, status=status, body=body):
                self.env.update(TEST_HTTP_CODE=status, TEST_RESPONSE=json.dumps(body))
                before = len(self.requests())
                result = self.run_script("--prompt", "loop", *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("--size auto", result.stderr)
                self.assertEqual(len(self.requests()), before + 1)

    def test_transport_failure_reports_uncertain_outcome_without_retry(self):
        self.env["TEST_TRANSPORT_ERROR"] = "1"
        result = self.run_script("--prompt", "test")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outcome may be unknown", result.stderr)
        self.assertEqual(len(self.requests()), 1)

    def test_invalid_responses_are_not_success_or_saved(self):
        invalid = [
            "", "<html>error</html>", "[]", '{"job_id":"job-1","status":"pending"}',
            '{"created":1,"credits_consumed":1,"data":[]}',
            '{"created":1,"credits_consumed":1,"data":[{}]}',
            RESPONSE.replace('"created": 1', '"created": true'),
            RESPONSE.replace('"credits_consumed": 1.25', '"credits_consumed": NaN'),
            RESPONSE.replace('"revised_prompt":null', '"revised_prompt":42'),
        ]
        target = self.root / "result.json"
        for body in invalid:
            with self.subTest(body=body):
                self.env["TEST_RESPONSE"] = body
                before = len(self.requests())
                result = self.run_script("--prompt", "test", "--output", str(target))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(target.exists())
                self.assertEqual(len(self.requests()), before + 1)

    def test_save_failure_keeps_completed_result_on_stdout(self):
        result = self.run_script("--prompt", "test", "--output", str(self.reference / "result.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Generation completed", result.stderr)
        self.assertEqual(result.stdout, RESPONSE)
        self.assertEqual(len(self.requests()), 1)


if __name__ == "__main__":
    unittest.main()
