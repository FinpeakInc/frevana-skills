import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
WRAPPER = PACKAGE / "scripts/browser_harness.sh"
UPSTREAM = "---\nname: browser-harness\ndescription: Upstream instructions\n---\n\n# Browser workflow\n"


class BrowserHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.jsonl"
        self.preference = self.root / "preference"
        self.target = self.root / "agent skills/browser-harness"
        self.env = os.environ.copy()
        self.env.update({"PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                         "MOCK_BIN": str(self.bin), "MOCK_LOG": str(self.log),
                         "MOCK_PREF": str(self.preference), "MOCK_UPSTREAM": UPSTREAM,
                         "BH_RECORD": "", "BU_AUTOSPAWN": "1", "BH_TELEMETRY": "1"})
        for name in ("uv", "browser-harness"):
            executable = self.bin / name
            executable.write_text("#!/usr/bin/env python3\n" + '''
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
code = sys.stdin.read() if name == "browser-harness" and not args else None
with open(os.environ["MOCK_LOG"], "a") as f:
    f.write(json.dumps({"name": name, "args": args, "code": code,
                        "telemetry": os.environ.get("BH_TELEMETRY"),
                        "autospawn": os.environ.get("BU_AUTOSPAWN"),
                        "prerelease": os.environ.get("UV_PRERELEASE"),
                        "record": os.environ.get("BH_RECORD")}) + "\\n")
if name == "uv":
    if args == ["tool", "dir", "--bin"]:
        print(os.environ["MOCK_BIN"])
    elif os.environ.get("MOCK_INSTALL_FAIL"):
        sys.exit(7)
elif args == ["skill"]:
    if os.environ.get("MOCK_SKILL_FAIL"):
        sys.exit(8)
    print(os.environ["MOCK_UPSTREAM"], end="")
elif args == ["--version"]:
    if os.environ.get("MOCK_VERSION_FAIL"):
        sys.exit(10)
    print("browser-harness test-version")
elif args == ["recordings"]:
    preference = pathlib.Path(os.environ["MOCK_PREF"])
    if os.environ.get("MOCK_UNKNOWN_STATUS"):
        print("future recording format")
    elif os.environ.get("BH_RECORD"):
        print("auto-recording: on (BH_RECORD)")
    elif preference.exists():
        print("auto-recording: " + preference.read_text() + " (config)")
    else:
        print("auto-recording: off (default)")
elif args[:1] == ["recordings"]:
    pathlib.Path(os.environ["MOCK_PREF"]).write_text("on" if args[1] == "enable" else "off")
elif not args:
    if os.environ.get("MOCK_CONNECT_FAIL"):
        print("permission-blocked", file=sys.stderr)
        sys.exit(9)
    print('{"url":"https://example.com","title":"Example"}')
''', encoding="utf-8")
            executable.chmod(0o755)

    def invoke(self, *args, code=None):
        return subprocess.run(["bash", str(WRAPPER), *args], input=code, text=True,
                              capture_output=True, env=self.env)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def setup_skill(self, *args):
        return self.invoke("setup", "--skill-dir", str(self.target), *args)

    def test_install_register_connect_and_pending_consent(self):
        result = self.setup_skill()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("[y/N]", result.stderr)
        self.assertFalse(self.preference.exists())
        self.assertEqual((self.target / "references/upstream-skill.md").read_text(), UPSTREAM)
        entry = (self.target / "SKILL.md").read_text()
        header, body = UPSTREAM.split("\n---\n", 1)
        self.assertTrue(entry.startswith(header + "\n---\n"))
        self.assertTrue(entry.endswith(body))
        self.assertIn("references/integration.md", entry)
        self.assertTrue((self.target / "scripts/browser_harness.py").is_file())
        calls = self.calls()
        self.assertEqual(calls[0]["args"], ["tool", "install", "--python", "3.12", "--upgrade", "--force", "browser-harness"])
        self.assertTrue(any(c["code"] == "print(page_info())\n" for c in calls))
        self.assertTrue(all(c["telemetry"] == "0" and c["autospawn"] == "" for c in calls))
        self.assertTrue(all(c["prerelease"] == "disallow" for c in calls))

    def test_explicit_yes_and_no_persist_choice(self):
        for choice, expected in (("yes", "on"), ("no", "off")):
            with self.subTest(choice=choice):
                self.preference.unlink(missing_ok=True)
                result = self.setup_skill("--recordings", choice)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.preference.read_text(), expected)

    def test_upgrade_preserves_saved_preference_even_with_opposite_choice(self):
        for saved, choice in (("on", "no"), ("off", "yes")):
            with self.subTest(saved=saved):
                self.preference.write_text(saved)
                result = self.setup_skill("--recordings", choice)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.preference.read_text(), saved)
        self.assertFalse(any(c["args"] in (["recordings", "enable"], ["recordings", "disable"]) for c in self.calls()))

    def test_environment_recording_preference_is_preserved(self):
        for value in ("0", "1"):
            with self.subTest(value=value):
                self.env["BH_RECORD"] = value
                result = self.setup_skill("--recordings", "no")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(self.preference.exists())
                self.assertEqual(self.calls()[-1]["record"], value)

    def test_consent_can_be_resolved_without_reinstall_or_connect(self):
        result = self.invoke("recordings", "--choice", "no")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.preference.read_text(), "off")
        self.assertFalse(any(c["code"] or c["args"][:2] == ["tool", "install"] for c in self.calls()))

    def test_failed_install_does_not_register_or_connect(self):
        self.env["MOCK_INSTALL_FAIL"] = "1"
        result = self.setup_skill()
        self.assertEqual(result.returncode, 7)
        self.assertFalse(self.target.exists())
        self.assertEqual(len(self.calls()), 1)

    def test_failed_connect_preserves_preference_and_reports_partial_setup(self):
        self.env["MOCK_CONNECT_FAIL"] = "1"
        self.preference.write_text("on")
        result = self.setup_skill()
        self.assertEqual(result.returncode, 9)
        self.assertTrue((self.target / "SKILL.md").is_file())
        self.assertEqual(self.preference.read_text(), "on")
        self.assertNotIn("Setup complete", result.stdout)
        self.assertIn("install.md", result.stderr)

    def test_invalid_upstream_output_leaves_registration_untouched(self):
        self.target.mkdir(parents=True)
        entry = self.target / "SKILL.md"
        entry.write_text("existing")
        self.env["MOCK_UPSTREAM"] = "update notice, not a skill"
        result = self.invoke("register", "--skill-dir", str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(entry.read_text(), "existing")

    def test_failed_skill_generation_leaves_registration_untouched(self):
        self.env["MOCK_SKILL_FAIL"] = "1"
        result = self.invoke("register", "--skill-dir", str(self.target))
        self.assertEqual(result.returncode, 8)
        self.assertFalse(self.target.exists())

    def test_unknown_recording_format_does_not_write_preference(self):
        self.env["MOCK_UNKNOWN_STATUS"] = "1"
        result = self.invoke("recordings", "--choice", "yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.preference.exists())

    def test_failed_version_probe_leaves_existing_entrypoint_and_references_untouched(self):
        self.target.mkdir(parents=True)
        (self.target / "SKILL.md").write_text("old entrypoint")
        self.env["MOCK_VERSION_FAIL"] = "1"
        result = self.invoke("register", "--skill-dir", str(self.target))
        self.assertEqual(result.returncode, 10)
        self.assertEqual((self.target / "SKILL.md").read_text(), "old entrypoint")
        self.assertFalse((self.target / "references").exists())

    def test_reregistration_replaces_official_instructions_without_duplicate_directives(self):
        result = self.invoke("register", "--skill-dir", str(self.target))
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = UPSTREAM + "\nNew upstream helper and workflow.\n"
        self.env["MOCK_UPSTREAM"] = updated
        result = subprocess.run(["bash", str(self.target / "scripts/browser_harness.sh"),
                                 "register", "--skill-dir", str(self.target)],
                                text=True, capture_output=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = (self.target / "SKILL.md").read_text()
        self.assertEqual(entry.count("## Frevana CLI integration"), 1)
        self.assertTrue(entry.endswith("New upstream helper and workflow.\n"))
        self.assertEqual((self.target / "references/upstream-skill.md").read_text(), updated)

    def test_official_cli_arguments_pass_through_without_shell_interpretation(self):
        cases = (("video", "export", "/tmp/a b $HOME `whoami`", "--reviewed"),
                 ("doctor", "--json", "--require-existing-daemon"),
                 ("auth", "status"), ("recordings", "--latest"), ("--help",))
        for cli_args in cases:
            with self.subTest(cli_args=cli_args):
                result = self.invoke("cli", "--", *cli_args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.calls()[-1]["args"], list(cli_args))

    def test_run_preserves_code_and_does_not_install(self):
        code = 'print("$HOME `whoami` 中文")\n'
        result = self.invoke("run", code=code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[-1]["code"], code)
        self.assertFalse(any(c["args"][:2] == ["tool", "install"] for c in self.calls()))
        script = self.root / "task with spaces.py"
        script.write_text(code)
        result = self.invoke("run", "--file", str(script))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[-1]["code"], code)

    def test_invalid_destination_rejected_before_install(self):
        result = self.invoke("setup", "--skill-dir", str(self.root))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_registered_package_is_independently_runnable_and_keeps_other_files(self):
        self.target.mkdir(parents=True)
        unrelated = self.target / "user-notes.md"
        unrelated.write_text("keep")
        result = self.invoke("register", "--skill-dir", str(self.target))
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(["bash", str(self.target / "scripts/browser_harness.sh"), "check"],
                                text=True, capture_output=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(unrelated.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
