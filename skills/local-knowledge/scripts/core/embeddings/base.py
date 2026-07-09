from pathlib import Path
from typing import Any, Dict, List, Protocol, Tuple

from core.errors import LocalKnowledgeError


class EmbeddingBackend(Protocol):
    name: str

    def load_model(self, model_name: str, data_dir: Path) -> Any:
        ...

    def encode_query(self, model: Any, model_name: str, query: str) -> List[float]:
        ...

    def encode_records(
        self,
        model: Any,
        records: List[Dict[str, Any]],
        batch_size: int = 32,
    ) -> List[List[float]]:
        ...


def import_runtime() -> Tuple[Any, Any]:
    try:
        import chromadb  # type: ignore
    except Exception as exc:
        raise LocalKnowledgeError("chromadb is required. Run doctor --install.") from exc
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:
        raise LocalKnowledgeError("sentence-transformers is required. Run doctor --install.") from exc
    return chromadb, SentenceTransformer


def vector_list(vectors: Any) -> List[List[float]]:
    return [v.tolist() if hasattr(v, "tolist") else list(v) for v in vectors]
