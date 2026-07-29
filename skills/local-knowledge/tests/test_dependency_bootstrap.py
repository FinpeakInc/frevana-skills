#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
WRAPPER = SKILL_DIR / "scripts" / "local_knowledge.sh"
PY_SCRIPT = SKILL_DIR / "scripts" / "local_knowledge.py"


FAKE_PYTHON = r"""#!/usr/bin/env python3
import os
import pathlib
import sys

state_dir = pathlib.Path(os.environ["FAKE_STATE_DIR"])
state_dir.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]

if args and args[0] == "-c":
    modules = set(args[2:])
    core = {"chromadb", "sentence_transformers", "socksio"}
    docs = {"pypdf", "docx", "openpyxl"}
    if modules and modules <= core:
        if (state_dir / "broken-core").exists():
            if "import_module" not in args[1]:
                raise SystemExit(0)
            raise SystemExit(1)
        raise SystemExit(0 if (state_dir / "core").exists() else 1)
    if modules and modules <= docs:
        raise SystemExit(0 if (state_dir / "docs").exists() else 1)
    raise SystemExit(1)

if args[:3] == ["-m", "pip", "install"]:
    with (state_dir / "pip.log").open("a", encoding="utf-8") as log:
        log.write(" ".join(args) + "\n")
    if "--upgrade" in args:
        raise SystemExit(0)
    requirement = pathlib.Path(args[args.index("-r") + 1]).name
    if requirement == "base.txt":
        (state_dir / "core").touch()
        (state_dir / "broken-core").unlink(missing_ok=True)
        raise SystemExit(0)
    if requirement == "docs.txt":
        if os.environ.get("FAKE_DOCS_INSTALL_FAIL") == "1":
            raise SystemExit(42)
        (state_dir / "docs").touch()
        raise SystemExit(0)
    raise SystemExit(0)

stub_roots = [pathlib.Path(os.environ["FAKE_CORE_STUBS"])]
if (state_dir / "docs").exists():
    stub_roots.insert(0, pathlib.Path(os.environ["FAKE_DOC_STUBS"]))
env = os.environ.copy()
existing = env.get("PYTHONPATH")
paths = [str(path) for path in stub_roots]
if existing:
    paths.append(existing)
env["PYTHONPATH"] = os.pathsep.join(paths)
os.execve(sys.executable, [sys.executable, *args], env)
"""


CHROMADB_STUB = r"""
_collections = {}


class Collection:
    def __init__(self):
        self.rows = {}

    def upsert(self, ids, documents, metadatas, embeddings):
        for index, row_id in enumerate(ids):
            self.rows[row_id] = (
                documents[index],
                metadatas[index],
                embeddings[index],
            )

    def count(self):
        return len(self.rows)


class PersistentClient:
    def __init__(self, path):
        self.path = path

    def delete_collection(self, name):
        key = (self.path, name)
        if key not in _collections:
            raise KeyError(name)
        del _collections[key]

    def get_or_create_collection(self, name, metadata=None):
        return _collections.setdefault((self.path, name), Collection())
"""


SENTENCE_TRANSFORMERS_STUB = r"""
class SentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass

    def encode(self, texts, **kwargs):
        return [[float(len(text)), 1.0] for text in texts]
"""


PYPDF_STUB = r"""
class Page:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class PdfReader:
    def __init__(self, path):
        with open(path, encoding="utf-8") as handle:
            self.pages = [Page(handle.read())]
"""


DOCX_STUB = r"""
class Paragraph:
    def __init__(self, text):
        self.text = text


class DocumentValue:
    def __init__(self, text):
        self.paragraphs = [Paragraph(text)]
        self.tables = []


def Document(path):
    with open(path, encoding="utf-8") as handle:
        return DocumentValue(handle.read())
"""


OPENPYXL_STUB = r"""
class Worksheet:
    title = "Smoke"

    def __init__(self, text):
        self.rows = [tuple(line.split("\t")) for line in text.splitlines()]

    def iter_rows(self, values_only=False):
        return iter(self.rows)


class Workbook:
    def __init__(self, text):
        self.worksheets = [Worksheet(text)]


def load_workbook(path, read_only=False, data_only=False):
    with open(path, encoding="utf-8") as handle:
        return Workbook(handle.read())
"""


class DependencyBootstrapSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="local-knowledge-smoke-")
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.venv_dir = self.data_dir / "venv"
        self.state_dir = self.root / "state"
        self.core_stubs = self.root / "stubs" / "core"
        self.doc_stubs = self.root / "stubs" / "docs"
        self.source_dir = self.root / "source"
        self.output_path = self.root / "result.json"

        (self.venv_dir / "bin").mkdir(parents=True)
        self.state_dir.mkdir()
        self.core_stubs.mkdir(parents=True)
        self.doc_stubs.mkdir(parents=True)
        self.source_dir.mkdir()

        self._write(self.venv_dir / "bin" / "python", FAKE_PYTHON, executable=True)
        self._write(self.core_stubs / "chromadb.py", CHROMADB_STUB)
        self._write(
            self.core_stubs / "sentence_transformers.py",
            SENTENCE_TRANSFORMERS_STUB,
        )
        self._write(self.core_stubs / "socksio.py", "")
        self._write(self.doc_stubs / "pypdf.py", PYPDF_STUB)
        self._write(self.doc_stubs / "docx.py", DOCX_STUB)
        self._write(self.doc_stubs / "openpyxl.py", OPENPYXL_STUB)

        self.env = os.environ.copy()
        self.env.update(
            {
                "LOCAL_KNOWLEDGE_DATA_DIR": str(self.data_dir),
                "LOCAL_KNOWLEDGE_VENV_DIR": str(self.venv_dir),
                "FAKE_STATE_DIR": str(self.state_dir),
                "FAKE_CORE_STUBS": str(self.core_stubs),
                "FAKE_DOC_STUBS": str(self.doc_stubs),
            }
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def _write(path: Path, content: str, executable: bool = False) -> None:
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
        if executable:
            path.chmod(0o755)

    def _run(self, *args: str, env=None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*args],
            cwd=self.root,
            env=env or self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def _wrapper(self, *args: str, env=None) -> subprocess.CompletedProcess[str]:
        return self._run("bash", str(WRAPPER), *args, env=env)

    def _read_result(self) -> dict:
        return json.loads(self.output_path.read_text(encoding="utf-8"))

    def _read_chunks(self, payload: dict) -> str:
        chunks_path = Path(payload["index_dir"]) / "chunks.jsonl"
        return chunks_path.read_text(encoding="utf-8")

    def _pip_log(self) -> list[str]:
        path = self.state_dir / "pip.log"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def test_bootstrap_installs_parsers_and_indexes_pdf_docx_xlsx(self) -> None:
        self._write(self.source_dir / "guide.pdf", "PDF_BOOTSTRAP_OK")
        self._write(self.source_dir / "notes.docx", "DOCX_BOOTSTRAP_OK")
        self._write(self.source_dir / "metrics.xlsx", "name\tvalue\nXLSX_BOOTSTRAP_OK\t3")

        result = self._wrapper(
            "index",
            "--path",
            str(self.source_dir),
            "--output",
            str(self.output_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self._read_result()
        self.assertEqual(payload["stats"]["file_count"], 3)
        self.assertEqual(payload["stats"]["skipped_count"], 0)
        chunks = self._read_chunks(payload)
        self.assertIn("PDF_BOOTSTRAP_OK", chunks)
        self.assertIn("DOCX_BOOTSTRAP_OK", chunks)
        self.assertIn("XLSX_BOOTSTRAP_OK", chunks)
        pip_log = self._pip_log()
        self.assertEqual(sum("base.txt" in line for line in pip_log), 1)
        self.assertEqual(sum("docs.txt" in line for line in pip_log), 1)

    def test_no_docs_install_keeps_text_only_core_usable(self) -> None:
        self._write(self.source_dir / "readme.txt", "TEXT_ONLY_CORE_OK")

        doctor = self._wrapper(
            "doctor",
            "--install",
            "--no-docs",
            "--output",
            str(self.output_path),
        )

        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        status = self._read_result()
        self.assertTrue(status["ok"])
        self.assertTrue(status["text_ok"])
        self.assertFalse(status["docs_required"])
        self.assertFalse(status["docs_ok"])
        self.assertFalse(status["degraded"])
        self.assertFalse(any("docs.txt" in line for line in self._pip_log()))

        index = self._run(
            str(self.venv_dir / "bin" / "python"),
            str(PY_SCRIPT),
            "index",
            "--data-dir",
            str(self.data_dir),
            "--path",
            str(self.source_dir),
            "--output",
            str(self.output_path),
        )
        self.assertEqual(index.returncode, 0, index.stderr)
        payload = self._read_result()
        self.assertEqual(payload["stats"]["file_count"], 1)
        self.assertEqual(payload["stats"]["skipped_count"], 0)
        self.assertIn("TEXT_ONLY_CORE_OK", self._read_chunks(payload))

    def test_broken_core_import_triggers_reinstall_before_indexing(self) -> None:
        (self.state_dir / "core").touch()
        (self.state_dir / "docs").touch()
        (self.state_dir / "broken-core").touch()
        self._write(self.source_dir / "readme.txt", "REPAIRED_CORE_OK")

        result = self._wrapper(
            "index",
            "--path",
            str(self.source_dir),
            "--output",
            str(self.output_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Core Local Knowledge dependencies are missing", result.stderr)
        self.assertFalse((self.state_dir / "broken-core").exists())
        self.assertEqual(sum("base.txt" in line for line in self._pip_log()), 1)
        payload = self._read_result()
        self.assertIn("REPAIRED_CORE_OK", self._read_chunks(payload))

    def test_failed_parser_install_degrades_and_skips_documents_once(self) -> None:
        (self.state_dir / "core").touch()
        self._write(self.source_dir / "readme.txt", "DEGRADED_TEXT_OK")
        self._write(self.source_dir / "guide.pdf", "unavailable pdf")
        self._write(self.source_dir / "notes.docx", "unavailable docx")
        self._write(self.source_dir / "metrics.xlsx", "unavailable xlsx")
        env = self.env.copy()
        env["FAKE_DOCS_INSTALL_FAIL"] = "1"

        result = self._wrapper(
            "index",
            "--path",
            str(self.source_dir),
            "--output",
            str(self.output_path),
            env=env,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("document dependency installation failed", result.stderr)
        self.assertIn("continuing in degraded mode", result.stderr)
        payload = self._read_result()
        self.assertEqual(payload["stats"]["file_count"], 1)
        self.assertEqual(payload["stats"]["skipped_count"], 3)
        self.assertIn("DEGRADED_TEXT_OK", self._read_chunks(payload))
        skipped = {Path(item["path"]).suffix: item["reason"] for item in payload["skipped"]}
        self.assertIn("pypdf", skipped[".pdf"])
        self.assertIn("python-docx", skipped[".docx"])
        self.assertIn("openpyxl", skipped[".xlsx"])
        self.assertEqual(sum("docs.txt" in line for line in self._pip_log()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
