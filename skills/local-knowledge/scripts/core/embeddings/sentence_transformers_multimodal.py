from pathlib import Path
from typing import Any, Dict, List

from core.embeddings.base import import_runtime, vector_list
from core.embeddings.sentence_transformers_text import SentenceTransformersTextBackend
from core.errors import LocalKnowledgeError


class SentenceTransformersMultimodalBackend(SentenceTransformersTextBackend):
    name = "sentence_transformers_multimodal"

    def load_model(self, model_name: str, data_dir: Path) -> Any:
        self.import_multimodal_runtime()
        _, SentenceTransformer = import_runtime()
        models_dir = data_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        kwargs = {"cache_folder": str(models_dir), "trust_remote_code": True}
        try:
            return SentenceTransformer(model_name, local_files_only=True, **kwargs)
        except Exception:
            return SentenceTransformer(model_name, **kwargs)

    def encode_records(
        self,
        model: Any,
        records: List[Dict[str, Any]],
        batch_size: int = 32,
    ) -> List[List[float]]:
        values: List[Any] = []
        for record in records:
            if record.get("modality") == "image":
                values.append({"text": record["text"], "image": record["source"]})
            else:
                values.append(record["text"])
        vectors = model.encode(
            values,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector_list(vectors)

    def import_multimodal_runtime(self) -> None:
        try:
            import PIL  # type: ignore  # noqa: F401
        except Exception as exc:
            raise LocalKnowledgeError("Multimodal mode requires Pillow. Run doctor --install --with-multimodal.") from exc
        try:
            import transformers  # type: ignore  # noqa: F401
        except Exception as exc:
            raise LocalKnowledgeError("Multimodal mode requires transformers. Run doctor --install --with-multimodal.") from exc
        try:
            import qwen_vl_utils  # type: ignore  # noqa: F401
        except Exception as exc:
            raise LocalKnowledgeError("Multimodal mode requires qwen-vl-utils. Run doctor --install --with-multimodal.") from exc
