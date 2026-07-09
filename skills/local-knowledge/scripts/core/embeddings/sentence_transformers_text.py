from pathlib import Path
from typing import Any, Dict, List

from core.embeddings.base import import_runtime, vector_list
from core.errors import LocalKnowledgeError


class SentenceTransformersTextBackend:
    name = "sentence_transformers_text"

    def load_model(self, model_name: str, data_dir: Path) -> Any:
        _, SentenceTransformer = import_runtime()
        models_dir = data_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        try:
            return SentenceTransformer(model_name, cache_folder=str(models_dir), local_files_only=True)
        except Exception:
            return SentenceTransformer(model_name, cache_folder=str(models_dir))

    def encode_query(self, model: Any, model_name: str, query: str) -> List[float]:
        return self.encode_texts(model, [self.query_text_for_model(model_name, query)], batch_size=1)[0]

    def encode_records(
        self,
        model: Any,
        records: List[Dict[str, Any]],
        batch_size: int = 32,
    ) -> List[List[float]]:
        values: List[str] = []
        for record in records:
            if record.get("modality") == "image":
                raise LocalKnowledgeError(f"Backend {self.name} cannot encode image records.")
            values.append(record["text"])
        return self.encode_texts(model, values, batch_size=batch_size)

    def encode_texts(self, model: Any, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector_list(vectors)

    def query_text_for_model(self, model_name: str, query: str) -> str:
        lowered = model_name.lower()
        if "bge" in lowered and "zh" in lowered:
            return f"为这个句子生成表示以用于检索相关文章：{query}"
        if "bge" in lowered and "m3" not in lowered:
            return f"Represent this sentence for searching relevant passages: {query}"
        return query
