import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "create_decision.sh"


class JevLatestCreateDecisionTests(unittest.TestCase):
    def run_script(self, *args: str, env=None):
        run_env = os.environ.copy() if env is None else env.copy()
        python_bin_dir = str(Path(sys.executable).parent)
        run_env["PATH"] = f"{python_bin_dir}{os.pathsep}{run_env.get('PATH', '')}"
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            text=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            env=run_env,
            check=False,
        )

    def fake_curl_env(self, temp: str, response=None):
        response = response or {
            "id": "decision-1",
            "answers": {"escalate": {"type": "noul", "noul": 0.91}},
            "model": "typesafe/jev-1.13-20260917",
            "provider": "TypeSafe",
            "usage": {"cost": 0.000016002, "inputTokens": 381, "outputTokens": 62},
        }
        temp_path = Path(temp)
        capture_path = temp_path / "request.json"
        args_path = temp_path / "curl-args.txt"
        fake_curl = temp_path / "curl"
        fake_curl.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
response=''
data_file=''
printf '%s\n' "$@" > "$FAKE_CURL_ARGS"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    *) shift ;;
  esac
done
cp "$data_file" "$FAKE_REQUEST_PATH"
printf '%s' "$FAKE_RESPONSE_JSON" > "$response"
printf '200'
""",
            encoding="utf-8",
        )
        fake_curl.chmod(0o755)
        env = os.environ.copy()
        python_bin_dir = str(Path(sys.executable).parent)
        env.update(
            {
                "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                "FREVANA_TOKEN": "test-token",
                "FAKE_REQUEST_PATH": str(capture_path),
                "FAKE_CURL_ARGS": str(args_path),
                "FAKE_RESPONSE_JSON": json.dumps(response),
            }
        )
        return env, capture_path, args_path

    def test_requires_state_and_questions(self):
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--state or --state-file", result.stderr)

    def test_rejects_invalid_model(self):
        result = self.run_script(
            "--model", "other/model", "--state", "ticket", "--questions", "{}"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid model", result.stderr)

    def test_rejects_invalid_question_shape_before_request(self):
        result = self.run_script(
            "--state",
            "ticket",
            "--questions",
            '{"priority":{"type":"score","instructions":"Rate it","criteria":{}}}',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("criteria array", result.stderr)

    def test_rejects_empty_score_criteria(self):
        result = self.run_script(
            "--state",
            "ticket",
            "--questions",
            '{"priority":{"type":"score","instructions":"Rate it","criteria":[]}}',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-empty criteria array", result.stderr)

    def test_rejects_user_longer_than_256_characters(self):
        result = self.run_script(
            "--state",
            "ticket",
            "--questions",
            "{}",
            "--user",
            "u" * 257,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at most 256 characters", result.stderr)

    def test_builds_request_and_sends_attribution(self):
        with tempfile.TemporaryDirectory() as temp:
            env, capture, args_path = self.fake_curl_env(temp)
            result = self.run_script(
                "--model",
                "jev-latest",
                "--state",
                "duplicate charge",
                "--questions",
                '{"escalate":{"type":"noul","instructions":"Escalate?"}}',
                "--session-id",
                "workflow-1",
                "--agent-app-instance-id",
                "app-instance-1",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            request = json.loads(capture.read_text(encoding="utf-8"))
            self.assertEqual(request["model"], "~typesafe/jev-latest")
            self.assertEqual(request["state"], "duplicate charge")
            self.assertEqual(request["sessionId"], "workflow-1")
            self.assertEqual(request["questions"]["escalate"]["type"], "noul")
            curl_args = args_path.read_text(encoding="utf-8")
            self.assertIn("/openrouter/v1/decisions", curl_args)
            self.assertIn("Authorization: Bearer test-token", curl_args)
            self.assertIn(
                "x-frevana-agent-app-instance-id: app-instance-1", curl_args
            )
            self.assertEqual(json.loads(result.stdout)["id"], "decision-1")

    def test_state_file_parses_json_and_answers_only_keeps_full_output(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            state_file = temp_path / "state.json"
            state_file.write_text('{"ticket":"duplicate charge"}', encoding="utf-8")
            output_file = temp_path / "result.json"
            env, capture, _ = self.fake_curl_env(temp)
            result = self.run_script(
                "--state-file",
                str(state_file),
                "--questions",
                '{"escalate":{"type":"noul","instructions":"Escalate?"}}',
                "--answers-only",
                "--output",
                str(output_file),
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(capture.read_text(encoding="utf-8"))["state"],
                {"ticket": "duplicate charge"},
            )
            self.assertEqual(
                json.loads(result.stdout),
                {"escalate": {"type": "noul", "noul": 0.91}},
            )
            self.assertEqual(
                json.loads(output_file.read_text(encoding="utf-8"))["id"],
                "decision-1",
            )

    def test_inline_state_parses_json_object(self):
        with tempfile.TemporaryDirectory() as temp:
            env, capture, _ = self.fake_curl_env(temp)
            result = self.run_script(
                "--state",
                '{"ticket":"duplicate charge"}',
                "--questions",
                '{"escalate":{"type":"noul","instructions":"Escalate?"}}',
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(capture.read_text(encoding="utf-8"))["state"],
                {"ticket": "duplicate charge"},
            )

    def test_raw_payload_forces_model(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            payload_file = temp_path / "payload.json"
            payload_file.write_text(
                json.dumps(
                    {
                        "model": "other/model",
                        "state": ["one", "two"],
                        "questions": {
                            "label": {
                                "type": "choice",
                                "instructions": "Choose",
                                "criteria": {"a": "First", "b": None},
                            },
                            "quality": {
                                "type": "score",
                                "instructions": "Score",
                                "criteria": ["poor", "good"],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            env, capture, _ = self.fake_curl_env(temp)
            result = self.run_script("--raw-payload-file", str(payload_file), env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(capture.read_text(encoding="utf-8"))["model"],
                "~typesafe/jev-latest",
            )

    def test_normalizes_official_wire_names_for_server_sdk(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            payload_file = temp_path / "payload.json"
            payload_file.write_text(
                json.dumps(
                    {
                        "model": "~typesafe/jev-latest",
                        "state": "ticket",
                        "questions": {},
                        "session_id": "session-1",
                        "provider": {
                            "allow_fallbacks": False,
                            "data_collection": "deny",
                            "enforce_distillable_text": True,
                            "max_price": {"request": "0.01"},
                            "preferred_max_latency": {"p50": 2},
                            "preferred_min_throughput": 100,
                            "require_parameters": True,
                            "zdr": True,
                        },
                        "trace": {
                            "trace_id": "trace-1",
                            "trace_name": "triage",
                            "custom_key": "custom-value",
                        },
                    }
                ),
                encoding="utf-8",
            )
            env, capture, _ = self.fake_curl_env(temp)
            result = self.run_script("--raw-payload-file", str(payload_file), env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            request = json.loads(capture.read_text(encoding="utf-8"))
            self.assertEqual(request["sessionId"], "session-1")
            self.assertNotIn("session_id", request)
            self.assertEqual(
                request["provider"],
                {
                    "allowFallbacks": False,
                    "dataCollection": "deny",
                    "enforceDistillableText": True,
                    "maxPrice": {"request": "0.01"},
                    "preferredMaxLatency": {"p50": 2},
                    "preferredMinThroughput": 100,
                    "requireParameters": True,
                    "zdr": True,
                },
            )
            self.assertEqual(
                request["trace"],
                {
                    "traceId": "trace-1",
                    "traceName": "triage",
                    "additionalProperties": {"custom_key": "custom-value"},
                },
            )

    def test_requires_token_when_unset(self):
        env = os.environ.copy()
        env.pop("FREVANA_TOKEN", None)
        result = self.run_script(
            "--state",
            "ticket",
            "--questions",
            '{"escalate":{"type":"noul","instructions":"Escalate?"}}',
            env=env,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Authentication required: set FREVANA_TOKEN or pass --token explicitly.", result.stderr)

    def test_token_override_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            env, capture, args_path = self.fake_curl_env(temp)
            env["FREVANA_TOKEN"] = "env-token"
            result = self.run_script(
                "--state",
                "ticket",
                "--questions",
                '{"escalate":{"type":"noul","instructions":"Escalate?"}}',
                "--token",
                "override-token",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            curl_args = args_path.read_text(encoding="utf-8")
            self.assertIn("Authorization: Bearer override-token", curl_args)
            self.assertNotIn("Authorization: Bearer env-token", curl_args)

    def test_rejects_api_key_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            env, _, _ = self.fake_curl_env(temp)
            result = self.run_script(
                "--state",
                "ticket",
                "--questions",
                '{"escalate":{"type":"noul","instructions":"Escalate?"}}',
                "--api-key",
                "some-key",
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unknown argument: --api-key", result.stderr)


if __name__ == "__main__":
    unittest.main()
