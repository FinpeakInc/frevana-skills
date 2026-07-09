import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import DEFAULT_MAX_FILE_MB, DEFAULT_MAX_FILES, DEFAULT_MODE
from core.errors import LocalKnowledgeError
from core.files import scan_file_fingerprints


def collection_name() -> str:
    return "local_knowledge"


def get_collection(chromadb: Any, chroma_path: Path, reset: bool = False) -> Any:
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    name = collection_name()
    if reset:
        try:
            client.delete_collection(name)
        except Exception:
            pass
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def collection_count(chromadb: Any, chroma_path: Path) -> int:
    collection = get_collection(chromadb, chroma_path, reset=False)
    try:
        return int(collection.count())
    except Exception as exc:
        raise LocalKnowledgeError(f"Chroma collection is unreadable: {exc}") from exc


def read_manifest(path: Path) -> Optional[Dict[str, Any]]:
    manifest = path / "manifest.json"
    if not manifest.exists():
        return None
    return json.loads(manifest.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")


def manifest_is_current(
    source: Path,
    manifest: Dict[str, Any],
    mode: str,
    model: str,
    backend: str,
    chunk_size: int,
    chunk_overlap: int,
    max_file_mb: int,
    max_files: int,
) -> Tuple[bool, str]:
    if manifest.get("mode", DEFAULT_MODE) != mode:
        return False, "mode changed"
    if manifest.get("model") != model:
        return False, "model changed"
    if manifest.get("backend") != backend:
        return False, "backend changed"
    if manifest.get("chunk_size") != chunk_size:
        return False, "chunk_size changed"
    if manifest.get("chunk_overlap") != chunk_overlap:
        return False, "chunk_overlap changed"
    if manifest.get("max_file_mb", DEFAULT_MAX_FILE_MB) != max_file_mb:
        return False, "max_file_mb changed"
    if manifest.get("max_files", DEFAULT_MAX_FILES) != max_files:
        return False, "max_files changed"
    current_files, current_skipped = scan_file_fingerprints(source, mode, max_file_mb, max_files)
    manifest_files = [{
        "path": item.get("path"),
        "relative_path": item.get("relative_path"),
        "sha256": item.get("sha256"),
        "mtime": item.get("mtime"),
        "size": item.get("size"),
        "modality": item.get("modality", "text"),
    } for item in manifest.get("files", [])]
    manifest_files.sort(key=lambda item: item.get("relative_path") or "")
    manifest_skipped = [{
        "path": item.get("path"),
        "reason": item.get("reason"),
    } for item in manifest.get("skipped", [])]
    manifest_skipped.sort(key=lambda item: item.get("path") or "")
    if current_files != manifest_files:
        return False, "source files changed"
    if current_skipped != manifest_skipped:
        return False, "skipped files changed"
    return True, "current"
