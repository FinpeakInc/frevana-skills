import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_FILE_MB,
    DEFAULT_MAX_FILES,
    DEFAULT_MODE,
    ENGINE,
    SKILL,
    index_dir,
    normalize_mode,
    path_hash,
)
from core.embeddings import encode_query, encode_records, import_runtime, load_model, resolve_backend, resolve_model
from core.errors import LocalKnowledgeError
from core.files import scan_documents
from core.io_utils import emit, json_dumps, utc_now
from core.store import collection_count, get_collection, manifest_is_current, read_manifest, write_jsonl


def cmd_doctor(args: argparse.Namespace) -> None:
    mode = normalize_mode(args.mode)
    checks: Dict[str, Any] = {
        "python": sys.version.split()[0],
        "data_dir": str(args.data_dir),
        "venv_dir": str(args.venv_dir) if args.venv_dir else None,
    }
    text_modules = ("chromadb", "sentence_transformers", "socksio")
    docs_modules = ("pypdf", "docx", "openpyxl")
    multimodal_modules = ("PIL", "transformers", "qwen_vl_utils", "timm", "einops", "accelerate")
    modules = (
        *text_modules,
        *docs_modules,
        *multimodal_modules,
    )
    for module in modules:
        try:
            __import__(module)
            checks[module] = True
        except Exception:
            checks[module] = False
    text_ok = all(bool(checks[module]) for module in text_modules)
    docs_ok = all(bool(checks[module]) for module in docs_modules)
    multimodal_ok = text_ok and all(bool(checks[module]) for module in multimodal_modules)
    docs_required = args.docs
    usable = multimodal_ok if mode == "multimodal" else text_ok
    degraded = usable and docs_required and not docs_ok
    ok = usable
    if mode == "multimodal" and not usable:
        message = "Run doctor --install --with-multimodal."
    elif not usable:
        message = "Run doctor --install."
    elif degraded:
        message = (
            "Environment is ready with reduced document support. "
            "Unavailable PDF, DOCX, or XLSX files will be skipped."
        )
    else:
        message = "Environment is ready."
    data = {
        "operation": "doctor",
        "skill": SKILL,
        "mode": mode,
        "ok": ok,
        "usable": usable,
        "degraded": degraded,
        "text_ok": text_ok,
        "docs_required": docs_required,
        "docs_ok": docs_ok,
        "multimodal_ok": multimodal_ok,
        "checks": checks,
        "message": message,
    }
    emit(data, args.output)


def perform_index(args: argparse.Namespace) -> Dict[str, Any]:
    source = Path(args.path).expanduser().resolve()
    if not source.is_dir() and not source.is_file():
        raise LocalKnowledgeError(f"Source path not found: {source}")
    data_dir = Path(args.data_dir).expanduser()
    mode = normalize_mode(args.mode)
    model_name = resolve_model(args.model, mode)
    backend = resolve_backend(model_name, mode, getattr(args, "backend", None))
    idx_dir = index_dir(data_dir, source, mode)
    tmp_dir = idx_dir.with_name(f".{idx_dir.name}.tmp-{os.getpid()}")
    chroma_dir = tmp_dir / "chroma"
    backup_dir: Optional[Path] = None
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.chunk_overlap >= args.chunk_size:
            raise LocalKnowledgeError("--chunk-overlap must be smaller than --chunk-size.")
        if args.max_file_mb <= 0:
            raise LocalKnowledgeError("--max-file-mb must be greater than 0.")
        if args.max_files <= 0:
            raise LocalKnowledgeError("--max-files must be greater than 0.")
        files_meta, chunks, skipped = scan_documents(
            source,
            mode,
            args.chunk_size,
            args.chunk_overlap,
            args.max_file_mb,
            args.max_files,
        )
        if not chunks:
            raise LocalKnowledgeError(f"No supported local-knowledge records found under: {source}")

        model = load_model(model_name, data_dir, backend)
        embeddings = encode_records(model, backend, chunks, batch_size=args.batch_size)

        chromadb, _ = import_runtime()
        collection = get_collection(chromadb, chroma_dir, reset=True)
        metadatas = [{
            "source": c["source"],
            "relative_path": c["relative_path"],
            "chunk_index": c["chunk_index"],
            "modality": c["modality"],
            "line_start": c["line_start"],
            "line_end": c["line_end"],
        } for c in chunks]
        collection.upsert(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=metadatas,
            embeddings=embeddings,
        )
        count = collection_count(chromadb, chroma_dir)
        if count != len(chunks):
            raise LocalKnowledgeError(f"Chroma index count mismatch: expected {len(chunks)}, got {count}")
        write_jsonl(tmp_dir / "chunks.jsonl", chunks)
        previous = read_manifest(idx_dir)
        manifest = {
            "skill": SKILL,
            "engine": ENGINE,
            "mode": mode,
            "source_path": str(source),
            "path_hash": path_hash(source),
            "model": model_name,
            "model_input": args.model,
            "backend": backend,
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
            "max_file_mb": args.max_file_mb,
            "max_files": args.max_files,
            "created_at": (previous or {}).get("created_at", utc_now()),
            "updated_at": utc_now(),
            "files": files_meta,
            "skipped": skipped,
            "stats": {
                "file_count": len(files_meta),
                "chunk_count": len(chunks),
                "skipped_count": len(skipped),
            },
        }
        (tmp_dir / "manifest.json").write_text(json_dumps(manifest) + "\n", encoding="utf-8")
        if idx_dir.exists():
            backup_dir = idx_dir.with_name(f".{idx_dir.name}.old-{os.getpid()}")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            idx_dir.rename(backup_dir)
            tmp_dir.rename(idx_dir)
            shutil.rmtree(backup_dir)
        else:
            tmp_dir.rename(idx_dir)
    except Exception:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        if backup_dir is not None and backup_dir.exists() and not idx_dir.exists():
            backup_dir.rename(idx_dir)
        raise
    return {
        "operation": "index",
        "skill": SKILL,
        "engine": ENGINE,
        "mode": mode,
        "source_path": str(source),
        "index_dir": str(idx_dir),
        "model": model_name,
        "backend": backend,
        "stats": manifest["stats"],
        "skipped": skipped,
        "manifest": manifest,
    }


def cmd_index(args: argparse.Namespace) -> None:
    data = perform_index(args)
    data.pop("manifest", None)
    emit(data, args.output)


def ensure_index(args: argparse.Namespace) -> Tuple[Path, Dict[str, Any]]:
    source = Path(args.path).expanduser().resolve()
    mode = normalize_mode(args.mode)
    idx_dir = index_dir(Path(args.data_dir).expanduser(), source, mode)
    manifest = read_manifest(idx_dir)
    if not manifest:
        raise LocalKnowledgeError(f"No local-knowledge index found for {source}. Run index first.")
    return idx_dir, manifest


def ensure_index_for_query(args: argparse.Namespace) -> Tuple[Path, Dict[str, Any], Optional[Dict[str, Any]]]:
    source = Path(args.path).expanduser().resolve()
    requested_mode = normalize_mode(args.mode)
    idx_dir = index_dir(Path(args.data_dir).expanduser(), source, requested_mode)
    manifest = read_manifest(idx_dir)
    auto_index_info: Optional[Dict[str, Any]] = None
    requested_model = resolve_model(args.model, requested_mode) if args.model else None
    effective_mode = requested_mode or (manifest or {}).get("mode", DEFAULT_MODE) or DEFAULT_MODE
    effective_model = requested_model or (manifest or {}).get("model") or resolve_model(None, effective_mode)
    requested_backend = resolve_backend(effective_model, effective_mode, getattr(args, "backend", None))
    effective_backend = requested_backend or (manifest or {}).get("backend")
    effective_chunk_size = args.chunk_size or (manifest or {}).get("chunk_size") or DEFAULT_CHUNK_SIZE
    effective_chunk_overlap = args.chunk_overlap
    if effective_chunk_overlap is None:
        effective_chunk_overlap = (manifest or {}).get("chunk_overlap") or DEFAULT_CHUNK_OVERLAP
    effective_max_file_mb = args.max_file_mb or (manifest or {}).get("max_file_mb") or DEFAULT_MAX_FILE_MB
    effective_max_files = args.max_files or (manifest or {}).get("max_files") or DEFAULT_MAX_FILES

    should_index = False
    reason = ""
    if not manifest:
        if not args.auto_index:
            raise LocalKnowledgeError(f"No local-knowledge index found for {source}. Run index first or pass --auto-index.")
        should_index = True
        reason = "missing index"
    elif requested_model and requested_model != manifest["model"]:
        if not args.auto_index:
            raise LocalKnowledgeError(
                f"Requested model {requested_model} differs from indexed model {manifest['model']}. "
                f"Re-run index with --model {args.model} or pass --auto-index."
            )
        should_index = True
        reason = "model changed"
    elif manifest and effective_backend != manifest.get("backend", resolve_backend(manifest["model"], manifest.get("mode", DEFAULT_MODE))):
        if not args.auto_index:
            raise LocalKnowledgeError(
                f"Requested backend {effective_backend} differs from indexed backend "
                f"{manifest.get('backend')}. Re-run index or pass --auto-index."
            )
        should_index = True
        reason = "backend changed"
    elif args.auto_index:
        is_current, current_reason = manifest_is_current(
            source,
            manifest,
            effective_mode,
            effective_model,
            effective_backend,
            effective_chunk_size,
            effective_chunk_overlap,
            effective_max_file_mb,
            effective_max_files,
        )
        should_index = not is_current
        reason = current_reason

    if manifest and not should_index:
        try:
            chromadb, _ = import_runtime()
            count = collection_count(chromadb, idx_dir / "chroma")
        except LocalKnowledgeError:
            if not args.auto_index:
                raise
            should_index = True
            reason = "chroma index unreadable"
        else:
            expected_count = int((manifest.get("stats") or {}).get("chunk_count") or 0)
            if expected_count > 0 and count != expected_count:
                if not args.auto_index:
                    raise LocalKnowledgeError(
                        f"Chroma index count mismatch: expected {expected_count}, got {count}. "
                        "Re-run index or pass --auto-index."
                    )
                should_index = True
                reason = "chroma index count mismatch"

    if should_index:
        index_args = argparse.Namespace(
            path=args.path,
            data_dir=args.data_dir,
            output=None,
            mode=effective_mode,
            model=args.model or (manifest or {}).get("model_input"),
            backend=effective_backend,
            chunk_size=effective_chunk_size,
            chunk_overlap=effective_chunk_overlap,
            batch_size=args.batch_size,
            max_file_mb=effective_max_file_mb,
            max_files=effective_max_files,
        )
        index_result = perform_index(index_args)
        manifest = index_result["manifest"]
        auto_index_info = {
            "ran": True,
            "reason": reason,
            "stats": index_result["stats"],
            "model": index_result["model"],
            "backend": index_result["backend"],
        }
    elif args.auto_index:
        auto_index_info = {"ran": False, "reason": reason or "current"}

    if not manifest:
        raise LocalKnowledgeError(f"No local-knowledge index found for {source}. Run index first.")
    return idx_dir, manifest, auto_index_info


def cmd_search_like(args: argparse.Namespace, operation: str) -> None:
    idx_dir, manifest, auto_index_info = ensure_index_for_query(args)
    mode = normalize_mode(args.mode)
    model_name = resolve_model(args.model, mode) if args.model else manifest["model"]
    backend = resolve_backend(model_name, mode, getattr(args, "backend", None))
    if mode != manifest.get("mode", DEFAULT_MODE):
        raise LocalKnowledgeError(
            f"Requested mode {mode} differs from indexed mode {manifest.get('mode', DEFAULT_MODE)}. "
            f"Re-run index with --mode {mode}."
        )
    if model_name != manifest["model"]:
        raise LocalKnowledgeError(
            f"Requested model {model_name} differs from indexed model {manifest['model']}. "
            f"Re-run index with --model {args.model}."
        )
    indexed_backend = manifest.get("backend", resolve_backend(manifest["model"], manifest.get("mode", DEFAULT_MODE)))
    if backend != indexed_backend:
        raise LocalKnowledgeError(
            f"Requested backend {backend} differs from indexed backend {indexed_backend}. Re-run index."
        )
    query = args.query if operation == "search" else args.question
    model = load_model(model_name, Path(args.data_dir).expanduser(), backend)
    query_vector = encode_query(model, backend, model_name, query)
    chromadb, _ = import_runtime()
    collection = get_collection(chromadb, idx_dir / "chroma", reset=False)
    result = collection.query(query_embeddings=[query_vector], n_results=args.top_k)
    matches: List[Dict[str, Any]] = []
    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    for cid, doc, meta, distance in zip(ids, docs, metas, distances):
        score = None
        if isinstance(distance, (int, float)):
            score = max(0.0, min(1.0, 1.0 - float(distance)))
        matches.append({
            "source": meta.get("source"),
            "relative_path": meta.get("relative_path"),
            "chunk_id": cid,
            "modality": meta.get("modality", "text"),
            "score": score,
            "distance": distance,
            "line_start": meta.get("line_start"),
            "line_end": meta.get("line_end"),
            "text": doc,
        })
    payload: Dict[str, Any] = {
        "operation": operation,
        "skill": SKILL,
        "engine": ENGINE,
        "mode": mode,
        "provider": "none" if operation == "ask" else None,
        "model": model_name,
        "backend": backend,
        "source_path": manifest["source_path"],
        "query": query if operation == "search" else None,
        "question": query if operation == "ask" else None,
        "top_k": args.top_k,
        "matches": matches,
    }
    if auto_index_info is not None:
        payload["auto_index"] = auto_index_info
    if operation == "ask":
        payload["answer"] = None
        payload["message"] = "provider=none; the calling agent should answer from matches."
    payload = {k: v for k, v in payload.items() if v is not None}
    emit(payload, args.output)


def cmd_status(args: argparse.Namespace) -> None:
    source = Path(args.path).expanduser().resolve()
    mode = normalize_mode(args.mode)
    idx_dir = index_dir(Path(args.data_dir).expanduser(), source, mode)
    manifest = read_manifest(idx_dir)
    emit({
        "operation": "status",
        "skill": SKILL,
        "mode": mode,
        "source_path": str(source),
        "indexed": manifest is not None,
        "index_dir": str(idx_dir),
        "manifest": manifest,
    }, args.output)


def cmd_delete(args: argparse.Namespace) -> None:
    source = Path(args.path).expanduser().resolve()
    mode = normalize_mode(args.mode)
    idx_dir = index_dir(Path(args.data_dir).expanduser(), source, mode)
    if not args.yes:
        raise LocalKnowledgeError("delete requires --yes.")
    existed = idx_dir.exists()
    if existed:
        shutil.rmtree(idx_dir)
    emit({
        "operation": "delete",
        "skill": SKILL,
        "mode": mode,
        "source_path": str(source),
        "index_dir": str(idx_dir),
        "deleted": existed,
    }, args.output)
