import hashlib
from pathlib import Path
from typing import Optional

from core.errors import LocalKnowledgeError


SKILL = "local-knowledge"
ENGINE = "chroma"
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MODE = "text"
DEFAULT_MULTIMODAL_MODEL = "Qwen/Qwen3-VL-Embedding-2B"

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".json", ".jsonl", ".csv", ".tsv", ".log",
    ".yaml", ".yml", ".html", ".htm", ".xml", ".py", ".js", ".jsx", ".ts",
    ".tsx", ".go", ".java", ".rs", ".sh", ".bash", ".zsh", ".css", ".scss",
    ".sql", ".toml", ".ini", ".env", ".conf", ".cfg", ".rb", ".php", ".c",
    ".h", ".cpp", ".hpp", ".cs", ".swift", ".kt", ".kts", ".dart", ".vue",
    ".svelte",
}
OPTIONAL_EXTS = {".pdf", ".doc", ".docx", ".xlsx"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv",
    "__pycache__", ".next", ".nuxt", ".svelte-kit", ".angular", ".turbo",
    ".parcel-cache", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".gradle", ".yarn", ".pnpm-store", "bower_components", "coverage", "dist",
    "build", "out", "target", "bin", "obj",
}
SKIP_FILE_NAMES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lock", "bun.lockb", "poetry.lock", "Pipfile.lock", "Gemfile.lock",
    "composer.lock", "go.sum", "Cargo.lock", "mix.lock",
}
SKIP_FILE_SUFFIXES = {
    ".map", ".lock", ".pyc", ".pyo", ".class", ".jar", ".war", ".ear", ".o",
    ".obj", ".so", ".dylib", ".dll", ".exe", ".bin", ".wasm", ".zip", ".tar",
    ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".whl",
}
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 160
DEFAULT_BATCH_SIZE = 32
DEFAULT_MAX_FILE_MB = 25
DEFAULT_MAX_FILES = 2000


def normalize_mode(mode: Optional[str]) -> str:
    value = mode or DEFAULT_MODE
    if value not in {"text", "multimodal"}:
        raise LocalKnowledgeError("--mode must be text or multimodal.")
    return value


def path_hash(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:24]


def index_dir(data_dir: Path, source_path: Path, mode: str = DEFAULT_MODE) -> Path:
    root = data_dir / "indexes"
    if mode == DEFAULT_MODE:
        return root / path_hash(source_path)
    return root / f"{mode}-{path_hash(source_path)}"
