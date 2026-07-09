from typing import Dict, Optional

from core.config import DEFAULT_MODE, DEFAULT_MODEL, DEFAULT_MULTIMODAL_MODEL
from core.embeddings.base import EmbeddingBackend
from core.embeddings.sentence_transformers_multimodal import SentenceTransformersMultimodalBackend
from core.embeddings.sentence_transformers_text import SentenceTransformersTextBackend
from core.errors import LocalKnowledgeError


BACKEND_ST_TEXT = "sentence_transformers_text"
BACKEND_ST_MULTIMODAL = "sentence_transformers_multimodal"

MODEL_ALIASES = {
    "default": DEFAULT_MODEL,
    "en-small": DEFAULT_MODEL,
    "zh-small": "BAAI/bge-small-zh-v1.5",
    "bge-m3": "BAAI/bge-m3",
    "qwen3-vl-2b": DEFAULT_MULTIMODAL_MODEL,
}
MODEL_BACKENDS: Dict[str, str] = {
    DEFAULT_MODEL: BACKEND_ST_TEXT,
    "BAAI/bge-small-zh-v1.5": BACKEND_ST_TEXT,
    "BAAI/bge-m3": BACKEND_ST_TEXT,
    DEFAULT_MULTIMODAL_MODEL: BACKEND_ST_MULTIMODAL,
}
MODE_DEFAULT_BACKENDS = {
    "text": BACKEND_ST_TEXT,
    "multimodal": BACKEND_ST_MULTIMODAL,
}
BACKEND_ADAPTERS: Dict[str, EmbeddingBackend] = {
    BACKEND_ST_TEXT: SentenceTransformersTextBackend(),
    BACKEND_ST_MULTIMODAL: SentenceTransformersMultimodalBackend(),
}


def resolve_model(model: Optional[str], mode: str = DEFAULT_MODE) -> str:
    if not model:
        return DEFAULT_MULTIMODAL_MODEL if mode == "multimodal" else DEFAULT_MODEL
    return MODEL_ALIASES.get(model, model)


def resolve_backend(model_name: str, mode: str = DEFAULT_MODE, backend: Optional[str] = None) -> str:
    if backend:
        get_backend(backend)
        return backend
    return MODEL_BACKENDS.get(model_name, MODE_DEFAULT_BACKENDS[mode])


def get_backend(backend: str) -> EmbeddingBackend:
    adapter = BACKEND_ADAPTERS.get(backend)
    if not adapter:
        raise LocalKnowledgeError(f"Unsupported embedding backend: {backend}")
    return adapter
