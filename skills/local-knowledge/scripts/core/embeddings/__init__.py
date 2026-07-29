from pathlib import Path
from typing import Any, Dict, List

from core.embeddings.base import import_runtime
from core.embeddings.registry import get_backend, resolve_backend, resolve_model


def load_model(model_name: str, data_dir: Path, backend: str) -> Any:
    return get_backend(backend).load_model(model_name, data_dir)


def encode_query(
    model: Any,
    backend: str,
    model_name: str,
    query: str,
) -> List[float]:
    return get_backend(backend).encode_query(model, model_name, query)


def encode_records(
    model: Any,
    backend: str,
    records: List[Dict[str, Any]],
    batch_size: int = 32,
) -> List[List[float]]:
    return get_backend(backend).encode_records(model, records, batch_size=batch_size)


__all__ = [
    "encode_query",
    "encode_records",
    "get_backend",
    "import_runtime",
    "load_model",
    "resolve_backend",
    "resolve_model",
]
