import csv
import hashlib
import html
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.config import (
    DEFAULT_MODE,
    IMAGE_EXTS,
    OPTIONAL_EXTS,
    SKIP_DIRS,
    SKIP_FILE_NAMES,
    SKIP_FILE_SUFFIXES,
    TEXT_EXTS,
)
from core.errors import LocalKnowledgeError


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def is_binary_sample(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            sample = f.read(4096)
    except OSError:
        return True
    return b"\x00" in sample


def safe_read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\n{3,}", "\n\n", raw)


def parse_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        raise LocalKnowledgeError("PDF support requires pypdf. Run doctor --install.") from exc
    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def parse_docx(path: Path) -> str:
    try:
        import docx  # type: ignore
    except Exception as exc:
        raise LocalKnowledgeError("DOCX support requires python-docx. Run doctor --install.") from exc
    doc = docx.Document(str(path))
    lines: List[str] = [p.text for p in doc.paragraphs if p.text]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                lines.append("\t".join(cells))
    return "\n".join(lines)


def parse_xlsx(path: Path) -> str:
    try:
        import openpyxl  # type: ignore
    except Exception as exc:
        raise LocalKnowledgeError("XLSX support requires openpyxl. Run doctor --install.") from exc
    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    lines: List[str] = []
    for sheet in workbook.worksheets:
        lines.append(f"# Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            values = ["" if value is None else str(value) for value in row]
            if any(values):
                lines.append("\t".join(values))
    return "\n".join(lines)


def parse_csv_like(path: Path, delimiter: str) -> str:
    text = safe_read_text(path)
    rows: List[str] = []
    try:
        reader = csv.reader(text.splitlines(), delimiter=delimiter)
        for row in reader:
            rows.append("\t".join(row))
    except csv.Error:
        return text
    return "\n".join(rows)


def parse_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix == ".xlsx":
        return parse_xlsx(path)
    if suffix == ".csv":
        return parse_csv_like(path, ",")
    if suffix == ".tsv":
        return parse_csv_like(path, "\t")
    text = safe_read_text(path)
    if suffix in {".html", ".htm", ".xml"}:
        return html_to_text(text)
    return text


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def optional_parser_error(path: Path) -> Optional[str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import pypdf  # type: ignore  # noqa: F401
        except Exception:
            return "PDF support requires pypdf. Run doctor --install."
    if suffix == ".docx":
        try:
            import docx  # type: ignore  # noqa: F401
        except Exception:
            return "DOCX support requires python-docx. Run doctor --install."
    if suffix == ".xlsx":
        try:
            import openpyxl  # type: ignore  # noqa: F401
        except Exception:
            return "XLSX support requires openpyxl. Run doctor --install."
    return None


def supported_exts(mode: str) -> set[str]:
    exts = set(TEXT_EXTS) | set(OPTIONAL_EXTS)
    if mode == "multimodal":
        exts |= IMAGE_EXTS
    return exts


def should_skip_file(lowered_name: str, suffix: str) -> bool:
    if lowered_name in SKIP_FILE_NAMES:
        return True
    if suffix in SKIP_FILE_SUFFIXES:
        return True
    if lowered_name.endswith((".min.js", ".min.css", ".bundle.js", ".bundle.css")):
        return True
    if lowered_name.endswith((".generated.js", ".generated.ts", ".generated.tsx")):
        return True
    return False


def iter_files(root: Path, mode: str = DEFAULT_MODE) -> Iterable[Path]:
    allowed = supported_exts(mode)
    if root.is_file():
        suffix = root.suffix.lower()
        lowered = root.name.lower()
        if not should_skip_file(lowered, suffix) and suffix in allowed:
            yield root
        return
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".local-knowledge")]
        for name in sorted(files):
            path = Path(current) / name
            suffix = path.suffix.lower()
            lowered = name.lower()
            if should_skip_file(lowered, suffix):
                continue
            if suffix in allowed:
                yield path


def relative_doc_path(source: Path, file_path: Path) -> str:
    if source.is_file():
        return file_path.name
    return str(file_path.relative_to(source))


def normalize_space(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def line_offsets(text: str) -> List[int]:
    offsets = [0]
    for match in re.finditer("\n", text):
        offsets.append(match.end())
    return offsets


def line_for_offset(offsets: List[int], offset: int) -> int:
    lo, hi = 0, len(offsets)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if offsets[mid] <= offset:
            lo = mid
        else:
            hi = mid
    return lo + 1


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[Tuple[str, int, int]]:
    text = normalize_space(text)
    if not text:
        return []
    if chunk_overlap >= chunk_size:
        raise LocalKnowledgeError("--chunk-overlap must be smaller than --chunk-size.")
    chunks: List[Tuple[str, int, int]] = []
    offsets = line_offsets(text)
    start = 0
    length = len(text)
    while start < length:
        target_end = min(length, start + chunk_size)
        end = target_end
        if target_end < length:
            window = text[start:target_end]
            candidates = [window.rfind("\n\n"), window.rfind("\n"), window.rfind(". "), window.rfind("。")]
            best = max(candidates)
            if best >= max(200, chunk_size // 3):
                end = start + best + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append((chunk, line_for_offset(offsets, start), line_for_offset(offsets, end)))
        if end >= length:
            break
        start = max(0, end - chunk_overlap)
    return chunks


def scan_documents(
    source: Path,
    mode: str,
    chunk_size: int,
    chunk_overlap: int,
    max_file_mb: int,
    max_files: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    files_meta: List[Dict[str, Any]] = []
    chunks: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    max_file_bytes = max_file_mb * 1024 * 1024
    accepted_files = 0
    for file_path in iter_files(source, mode):
        try:
            stat = file_path.stat()
            if accepted_files >= max_files:
                skipped.append({"path": str(file_path), "reason": f"max_files exceeded ({max_files})"})
                continue
            if stat.st_size > max_file_bytes:
                skipped.append({"path": str(file_path), "reason": f"file larger than --max-file-mb ({max_file_mb})"})
                continue
            if file_path.suffix.lower() in TEXT_EXTS and is_binary_sample(file_path):
                skipped.append({"path": str(file_path), "reason": "binary"})
                continue
            digest = sha256_file(file_path)
            rel = relative_doc_path(source, file_path)
            if is_image_file(file_path):
                if mode != "multimodal":
                    skipped.append({"path": str(file_path), "reason": "image requires --mode multimodal"})
                    continue
                file_chunks = [(f"[image] {rel}", 1, 1)]
            else:
                text = parse_file(file_path)
                file_chunks = chunk_text(text, chunk_size, chunk_overlap)
            file_meta = {
                "path": str(file_path.resolve()),
                "relative_path": rel,
                "sha256": digest,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "modality": "image" if is_image_file(file_path) else "text",
                "chunks": len(file_chunks),
            }
            files_meta.append(file_meta)
            accepted_files += 1
            for idx, (chunk, line_start, line_end) in enumerate(file_chunks):
                chunk_id_seed = f"{rel}:{digest}:{idx}:{line_start}:{line_end}"
                chunk_id = hashlib.sha256(chunk_id_seed.encode("utf-8")).hexdigest()[:32]
                chunks.append({
                    "id": chunk_id,
                    "source": str(file_path.resolve()),
                    "relative_path": rel,
                    "chunk_index": idx,
                    "modality": "image" if is_image_file(file_path) else "text",
                    "line_start": line_start,
                    "line_end": line_end,
                    "text": chunk,
                })
        except Exception as exc:
            skipped.append({"path": str(file_path), "reason": str(exc)})
    return files_meta, chunks, skipped


def scan_file_fingerprints(
    source: Path,
    mode: str,
    max_file_mb: int,
    max_files: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    files_meta: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    max_file_bytes = max_file_mb * 1024 * 1024
    accepted_files = 0
    for file_path in iter_files(source, mode):
        try:
            stat = file_path.stat()
            if accepted_files >= max_files:
                skipped.append({"path": str(file_path), "reason": f"max_files exceeded ({max_files})"})
                continue
            if stat.st_size > max_file_bytes:
                skipped.append({"path": str(file_path), "reason": f"file larger than --max-file-mb ({max_file_mb})"})
                continue
            if file_path.suffix.lower() in TEXT_EXTS and is_binary_sample(file_path):
                skipped.append({"path": str(file_path), "reason": "binary"})
                continue
            if not is_image_file(file_path):
                parser_error = optional_parser_error(file_path)
                if parser_error:
                    skipped.append({"path": str(file_path), "reason": parser_error})
                    continue
            files_meta.append({
                "path": str(file_path.resolve()),
                "relative_path": relative_doc_path(source, file_path),
                "sha256": sha256_file(file_path),
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "modality": "image" if is_image_file(file_path) else "text",
            })
            accepted_files += 1
        except Exception as exc:
            skipped.append({"path": str(file_path), "reason": str(exc)})
    files_meta.sort(key=lambda item: item["relative_path"])
    skipped.sort(key=lambda item: item["path"])
    return files_meta, skipped
