#!/usr/bin/env python3

import ctypes
import hashlib
import signal
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from core.files import (  # noqa: E402
    WORD_COM_HELPER,
    find_legacy_doc_parsers,
    is_word_process,
    iter_files,
    optional_parser_error,
    parse_doc,
    python_document_parser_signature,
    scan_documents,
    word_com_available,
)
from core.errors import LocalKnowledgeError  # noqa: E402
from core.store import manifest_is_current  # noqa: E402
from core.word_com import extract_story_text, extract_text  # noqa: E402


class LegacyDocTests(unittest.TestCase):
    def test_doc_extension_is_discovered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="local-knowledge-doc-discovery-") as tmp:
            source = Path(tmp)
            doc_path = source / "legacy.doc"
            doc_path.write_bytes(b"legacy")

            self.assertEqual(list(iter_files(source)), [doc_path])

    def test_missing_legacy_parser_has_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="local-knowledge-doc-missing-") as tmp:
            doc_path = Path(tmp) / "legacy.doc"
            doc_path.write_bytes(b"legacy")
            with (
                mock.patch("core.files.word_com_available", return_value=False),
                mock.patch("core.files.shutil.which", return_value=None),
            ):
                error = optional_parser_error(doc_path)

            self.assertIsNotNone(error)
            self.assertIn("textutil", error)
            self.assertIn("antiword", error)
            self.assertIn("catdoc", error)
            self.assertIn("Microsoft Word", error)
            self.assertIn("pywin32", error)

    def test_windows_word_com_parser_is_preferred(self) -> None:
        with (
            mock.patch("core.files.word_com_available", return_value=True),
            mock.patch(
                "core.files.shutil.which",
                side_effect=lambda name: "C:/antiword.exe" if name == "antiword" else None,
            ),
        ):
            parsers = find_legacy_doc_parsers()

        self.assertEqual(
            parsers,
            [
                ("word-com", sys.executable),
                ("antiword", "C:/antiword.exe"),
            ],
        )

    def test_windows_word_com_requires_registered_word(self) -> None:
        pythoncom = ModuleType("pythoncom")
        client = ModuleType("win32com.client")
        win32com = ModuleType("win32com")
        win32com.client = client  # type: ignore[attr-defined]
        pythoncom.CLSIDFromProgID = mock.Mock(side_effect=RuntimeError("not registered"))  # type: ignore[attr-defined]
        with (
            mock.patch("core.files.sys.platform", "win32"),
            mock.patch.dict(
                sys.modules,
                {
                    "pythoncom": pythoncom,
                    "win32com": win32com,
                    "win32com.client": client,
                },
            ),
        ):
            self.assertFalse(word_com_available())

    def test_parser_failure_falls_back_to_next_available_parser(self) -> None:
        failed = SimpleNamespace(returncode=1, stdout=b"", stderr=b"unsupported")
        succeeded = SimpleNamespace(returncode=0, stdout=b"FALLBACK_DOC_OK", stderr=b"")
        with tempfile.TemporaryDirectory(prefix="local-knowledge-doc-fallback-") as tmp:
            doc_path = Path(tmp) / "legacy.doc"
            doc_path.write_bytes(b"legacy")
            with (
                mock.patch(
                    "core.files.find_legacy_doc_parsers",
                    return_value=[
                        ("textutil", "/usr/bin/textutil"),
                        ("antiword", "/usr/bin/antiword"),
                    ],
                ),
                mock.patch("core.files.subprocess.run", side_effect=[failed, succeeded]) as run,
            ):
                parsed = parse_doc(doc_path)

            self.assertEqual(parsed, "FALLBACK_DOC_OK")
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args_list[1].args[0], ["/usr/bin/antiword", str(doc_path)])

    def test_word_com_failure_falls_back_to_antiword(self) -> None:
        failed = SimpleNamespace(returncode=1, stdout=b"", stderr=b"Word is not installed")
        succeeded = SimpleNamespace(returncode=0, stdout=b"ANTIWORD_OK", stderr=b"")
        with tempfile.TemporaryDirectory(prefix="local-knowledge-word-com-fallback-") as tmp:
            doc_path = Path(tmp) / "legacy.doc"
            doc_path.write_bytes(b"legacy")
            with (
                mock.patch(
                    "core.files.find_legacy_doc_parsers",
                    return_value=[
                        ("word-com", sys.executable),
                        ("antiword", "/usr/bin/antiword"),
                    ],
                ),
                mock.patch("core.files.subprocess.run", side_effect=[failed, succeeded]) as run,
            ):
                parsed = parse_doc(doc_path)

        self.assertEqual(parsed, "ANTIWORD_OK")
        self.assertEqual(
            run.call_args_list[0].args[0][:3],
            [sys.executable, str(WORD_COM_HELPER), str(doc_path)],
        )
        self.assertTrue(run.call_args_list[0].args[0][3].endswith("word.pid"))

    def test_word_com_helper_disables_macros_and_closes_word(self) -> None:
        events: list[object] = []

        class FakeDocument:
            Content = SimpleNamespace(Text="WORD_COM_OK")

            def Close(self, **kwargs: object) -> None:
                events.append(("close", kwargs))

        class FakeDocuments:
            def __init__(self, word: object) -> None:
                self.word = word

            def Open(self, **kwargs: object) -> FakeDocument:
                events.append(("open", kwargs))
                events.append((
                    "open_security",
                    self.word.AutomationSecurity,
                    self.word.Options.UpdateLinksAtOpen,
                ))
                return FakeDocument()

        class FakeWord:
            def __init__(self) -> None:
                self.Hwnd = 123
                self.Options = SimpleNamespace(UpdateLinksAtOpen=True)
                self.Visible = True
                self.DisplayAlerts = 1
                self.AutomationSecurity = 0
                self.Documents = FakeDocuments(self)

            def Quit(self, **kwargs: object) -> None:
                events.append(("quit", kwargs))

        word = FakeWord()
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = lambda: events.append("initialize")  # type: ignore[attr-defined]
        pythoncom.CoUninitialize = lambda: events.append("uninitialize")  # type: ignore[attr-defined]
        client = ModuleType("win32com.client")
        client.DispatchEx = lambda name: events.append(("dispatch", name)) or word  # type: ignore[attr-defined]
        win32com = ModuleType("win32com")
        win32com.client = client  # type: ignore[attr-defined]
        win32process = ModuleType("win32process")
        win32process.GetWindowThreadProcessId = lambda hwnd: (1, 4242)  # type: ignore[attr-defined]

        with tempfile.TemporaryDirectory(prefix="local-knowledge-word-com-helper-") as tmp:
            doc_path = Path(tmp) / "legacy.doc"
            pid_file = Path(tmp) / "word.pid"
            doc_path.write_bytes(b"legacy")
            with mock.patch.dict(
                sys.modules,
                {
                    "pythoncom": pythoncom,
                    "win32com": win32com,
                    "win32com.client": client,
                    "win32process": win32process,
                },
            ):
                text = extract_text(doc_path, pid_file)

        self.assertEqual(text, "WORD_COM_OK")
        self.assertFalse(word.Visible)
        self.assertEqual(word.DisplayAlerts, 0)
        self.assertIn(("open_security", 3, False), events)
        self.assertEqual(word.AutomationSecurity, 0)
        self.assertTrue(word.Options.UpdateLinksAtOpen)
        self.assertFalse(pid_file.exists())
        open_event = next(event for event in events if isinstance(event, tuple) and event[0] == "open")
        self.assertEqual(
            open_event[1],
            {
                "FileName": str(doc_path.resolve()),
                "ConfirmConversions": False,
                "ReadOnly": True,
                "AddToRecentFiles": False,
                "Visible": False,
                "OpenAndRepair": False,
                "NoEncodingDialog": True,
            },
        )
        self.assertIn(("close", {"SaveChanges": False}), events)
        self.assertIn(("quit", {"SaveChanges": False}), events)
        self.assertEqual(events[-1], "uninitialize")

    def test_word_com_timeout_terminates_only_recorded_word_process(self) -> None:
        def timeout(command: list[str], **kwargs: object) -> None:
            Path(command[3]).write_text("4242", encoding="ascii")
            raise subprocess.TimeoutExpired(command, 120)

        with tempfile.TemporaryDirectory(prefix="local-knowledge-word-com-timeout-") as tmp:
            doc_path = Path(tmp) / "legacy.doc"
            doc_path.write_bytes(b"legacy")
            with (
                mock.patch(
                    "core.files.find_legacy_doc_parsers",
                    return_value=[("word-com", sys.executable)],
                ),
                mock.patch("core.files.subprocess.run", side_effect=timeout),
                mock.patch("core.files.sys.platform", "win32"),
                mock.patch("core.files.is_word_process", return_value=True),
                mock.patch("core.files.os.kill") as kill,
            ):
                with self.assertRaisesRegex(LocalKnowledgeError, "timed out"):
                    parse_doc(doc_path)

        kill.assert_called_once_with(4242, signal.SIGTERM)

    def test_word_process_identity_is_verified_before_termination(self) -> None:
        class FakeFunction:
            def __init__(self, callback: object) -> None:
                self.callback = callback
                self.argtypes = None
                self.restype = None

            def __call__(self, *args: object) -> object:
                return self.callback(*args)  # type: ignore[operator]

        closed: list[object] = []

        def query_image(
            handle: object,
            flags: object,
            buffer: object,
            size: object,
        ) -> bool:
            del handle, flags, size
            buffer.value = "C:/Program Files/Microsoft Office/WINWORD.EXE"
            return True

        kernel32 = SimpleNamespace(
            OpenProcess=FakeFunction(lambda *args: 99),
            QueryFullProcessImageNameW=FakeFunction(query_image),
            CloseHandle=FakeFunction(lambda handle: closed.append(handle) or True),
        )
        with (
            mock.patch("core.files.sys.platform", "win32"),
            mock.patch.object(ctypes, "WinDLL", return_value=kernel32, create=True),
        ):
            self.assertTrue(is_word_process(4242))
        self.assertEqual(closed, [99])

    def test_word_com_extracts_all_story_ranges(self) -> None:
        class FakeStory:
            def __init__(
                self,
                story_type: int,
                start: int,
                end: int,
                text: str,
                next_story: object = None,
            ) -> None:
                self.StoryType = story_type
                self.Start = start
                self.End = end
                self.Text = text
                self.NextStoryRange = next_story

        third_header = FakeStory(7, 0, 9, "THIRD_HEADER")
        duplicate_header = FakeStory(7, 0, 8, "FIRST_HEADER", third_header)
        first_header = FakeStory(7, 0, 8, "FIRST_HEADER", duplicate_header)
        main = FakeStory(1, 0, 9, "MAIN_BODY")
        footnote = FakeStory(2, 0, 8, "FOOTNOTE")
        document = SimpleNamespace(
            Content=SimpleNamespace(Text="MAIN_BODY"),
            StoryRanges=[main, first_header, footnote],
        )

        text = extract_story_text(document)

        self.assertIn("MAIN_BODY", text)
        self.assertIn("FIRST_HEADER", text)
        self.assertEqual(text.count("FIRST_HEADER"), 1)
        self.assertIn("THIRD_HEADER", text)
        self.assertIn("FOOTNOTE", text)

    def test_python_document_parser_signature_tracks_import_health(self) -> None:
        spec = SimpleNamespace(origin="/same/pypdf/__init__.py")

        def find_spec(module: str) -> object:
            return spec if module == "pypdf" else None

        def broken_import(module: str) -> object:
            if module == "pypdf":
                raise ImportError("broken dependency")
            return object()

        with (
            mock.patch("core.files.importlib.util.find_spec", side_effect=find_spec),
            mock.patch("core.files.Path.stat", side_effect=OSError),
            mock.patch("core.files.importlib.import_module", side_effect=broken_import),
        ):
            broken = python_document_parser_signature()
        with (
            mock.patch("core.files.importlib.util.find_spec", side_effect=find_spec),
            mock.patch("core.files.Path.stat", side_effect=OSError),
            mock.patch("core.files.importlib.import_module", return_value=object()),
        ):
            healthy = python_document_parser_signature()

        self.assertFalse(broken[0]["import_ok"])
        self.assertTrue(healthy[0]["import_ok"])
        self.assertEqual(broken[0]["path"], healthy[0]["path"])

    def test_unchanged_failed_doc_does_not_repeat_auto_index(self) -> None:
        signature = [{"name": "textutil", "path": "/usr/bin/false"}]
        with tempfile.TemporaryDirectory(prefix="local-knowledge-doc-stable-skip-") as tmp:
            source = Path(tmp)
            doc_path = source / "broken.doc"
            doc_path.write_bytes(b"not a valid word document")
            with (
                mock.patch(
                    "core.files.find_legacy_doc_parsers",
                    return_value=[("textutil", "/usr/bin/false")],
                ),
                mock.patch("core.files.legacy_doc_parser_signature", return_value=signature),
            ):
                files, _, skipped = scan_documents(source, "text", 1200, 160, 25, 2000)
            manifest = {
                "mode": "text",
                "model": "model",
                "backend": "backend",
                "chunk_size": 1200,
                "chunk_overlap": 160,
                "max_file_mb": 25,
                "max_files": 2000,
                "legacy_doc_parsers": signature,
                "files": files,
                "skipped": skipped,
            }
            with mock.patch("core.store.legacy_doc_parser_signature", return_value=signature):
                current = manifest_is_current(
                    source, manifest, "text", "model", "backend", 1200, 160, 25, 2000
                )

            self.assertEqual(current, (True, "current"))
            self.assertEqual(len(skipped), 1)
            self.assertIn("sha256", skipped[0])

    def test_parser_signature_change_invalidates_doc_index(self) -> None:
        with tempfile.TemporaryDirectory(prefix="local-knowledge-doc-signature-") as tmp:
            source = Path(tmp)
            doc_path = source / "legacy.doc"
            doc_path.write_bytes(b"legacy")
            stat = doc_path.stat()
            manifest = {
                "mode": "text",
                "model": "model",
                "backend": "backend",
                "chunk_size": 1200,
                "chunk_overlap": 160,
                "max_file_mb": 25,
                "max_files": 2000,
                "legacy_doc_parsers": [{"name": "textutil", "path": "/old/textutil"}],
                "files": [{
                    "path": str(doc_path.resolve()),
                    "relative_path": "legacy.doc",
                    "sha256": hashlib.sha256(doc_path.read_bytes()).hexdigest(),
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "modality": "text",
                }],
                "skipped": [],
            }
            with mock.patch(
                "core.store.legacy_doc_parser_signature",
                return_value=[{"name": "antiword", "path": "/usr/bin/antiword"}],
            ):
                current = manifest_is_current(
                    source, manifest, "text", "model", "backend", 1200, 160, 25, 2000
                )

            self.assertEqual(current, (False, "legacy DOC parser changed"))

    def test_python_document_parser_change_invalidates_index(self) -> None:
        with tempfile.TemporaryDirectory(prefix="local-knowledge-parser-signature-") as tmp:
            source = Path(tmp)
            pdf_path = source / "guide.pdf"
            pdf_path.write_bytes(b"pdf")
            stat = pdf_path.stat()
            manifest = {
                "mode": "text",
                "model": "model",
                "backend": "backend",
                "chunk_size": 1200,
                "chunk_overlap": 160,
                "max_file_mb": 25,
                "max_files": 2000,
                "python_document_parsers": [],
                "files": [{
                    "path": str(pdf_path.resolve()),
                    "relative_path": "guide.pdf",
                    "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "modality": "text",
                }],
                "skipped": [],
            }
            with mock.patch(
                "core.store.python_document_parser_signature",
                return_value=[{"extension": ".pdf", "module": "pypdf", "path": "/pypdf.py"}],
            ):
                current = manifest_is_current(
                    source, manifest, "text", "model", "backend", 1200, 160, 25, 2000
                )

            self.assertEqual(current, (False, "document parser changed"))

    def test_unrelated_python_parser_change_keeps_index_current(self) -> None:
        with tempfile.TemporaryDirectory(prefix="local-knowledge-parser-scope-") as tmp:
            source = Path(tmp)
            pdf_path = source / "guide.pdf"
            pdf_path.write_bytes(b"pdf")
            stat = pdf_path.stat()
            pdf_signature = {
                "extension": ".pdf",
                "module": "pypdf",
                "import_ok": True,
                "path": "/pypdf.py",
            }
            manifest = {
                "mode": "text",
                "model": "model",
                "backend": "backend",
                "chunk_size": 1200,
                "chunk_overlap": 160,
                "max_file_mb": 25,
                "max_files": 2000,
                "python_document_parsers": [
                    pdf_signature,
                    {"extension": ".xlsx", "module": "openpyxl", "path": "/old.py"},
                ],
                "files": [{
                    "path": str(pdf_path.resolve()),
                    "relative_path": "guide.pdf",
                    "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "modality": "text",
                }],
                "skipped": [],
            }
            with mock.patch(
                "core.store.python_document_parser_signature",
                return_value=[
                    pdf_signature,
                    {"extension": ".xlsx", "module": "openpyxl", "path": "/new.py"},
                ],
            ):
                current = manifest_is_current(
                    source, manifest, "text", "model", "backend", 1200, 160, 25, 2000
                )

            self.assertEqual(current, (True, "current"))

    @unittest.skipUnless(shutil.which("textutil"), "requires macOS textutil")
    def test_real_binary_doc_is_parsed_with_textutil(self) -> None:
        with tempfile.TemporaryDirectory(prefix="local-knowledge-real-doc-") as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            text_path = root / "fixture.txt"
            doc_path = source / "fixture.doc"
            text_path.write_text("REAL_LEGACY_DOC_OK\n", encoding="utf-8")
            conversion = subprocess.run(
                [
                    shutil.which("textutil") or "textutil",
                    "-convert",
                    "doc",
                    "-output",
                    str(doc_path),
                    str(text_path),
                ],
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(
                conversion.returncode,
                0,
                conversion.stderr.decode("utf-8", errors="replace"),
            )
            self.assertTrue(doc_path.read_bytes().startswith(b"\xd0\xcf\x11\xe0"))

            parsed = parse_doc(doc_path)
            files, chunks, skipped = scan_documents(
                source,
                mode="text",
                chunk_size=1200,
                chunk_overlap=160,
                max_file_mb=25,
                max_files=2000,
            )

            self.assertIn("REAL_LEGACY_DOC_OK", parsed)
            self.assertEqual(len(files), 1)
            self.assertEqual(skipped, [])
            self.assertEqual(files[0]["relative_path"], "fixture.doc")
            self.assertIn("REAL_LEGACY_DOC_OK", chunks[0]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
