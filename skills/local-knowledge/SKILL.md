---
name: local-knowledge
description: Use when the user wants to query specific information inside a local directory or file, turn local documents into a private local knowledge base, install local embedding dependencies, index files with a local sentence-transformers-compatible embedding model, search relevant passages, or retrieve context for an agent to answer questions without uploading source documents by default.
---

# Local Knowledge

Build and query a private local knowledge base from a local directory or file.

## Purpose

Use this skill when the user wants:

- to point an agent at a local folder of documents
- to search for specific information inside a local directory or a single local file
- to build a local semantic index for that folder or file
- to search local knowledge by natural-language query
- to retrieve relevant context so the agent can answer from local files
- to install and use a local embedding model without installing Ollama or running a local LLM

The skill uses a local embedding model through `sentence-transformers` and stores a local Chroma index.

Default mode is `text`. Multimodal retrieval is an advanced opt-in mode and only runs when the user explicitly passes `--mode multimodal`.

## Privacy and Boundary Rules

- Source documents stay in the user's local folder.
- Chunks, embeddings, Chroma index data, and manifest files are stored locally.
- `index`, `search`, and default `ask` do not call a remote model provider.
- The first install/index run may download Python packages and a sentence-transformers-compatible embedding model.
- Multimodal dependencies and multimodal embedding models are not installed or downloaded unless the user explicitly chooses multimodal mode.
- The downloaded model is an embedding model, not a local chat/generation LLM.
- Do not install or call Ollama.
- Do not run a local LLM.
- `ask` defaults to `provider=none` and returns retrieved context only. The calling agent reads that context and writes the final answer.
- If a future remote answer provider is added, it must be explicitly requested and must clearly state that only retrieved chunks are sent.

## What This Skill Needs

Required:

- `bash`
- `python3`
- local folder or file path to index or search

Installed by `doctor --install` into a skill-owned virtual environment:

- core packages listed in `requirements/base.txt`

Optional document parsing dependencies installed by the same command:

- document packages listed in `requirements/docs.txt`

Optional multimodal dependencies installed only when requested:

- multimodal packages listed in `requirements/multimodal.txt`

Dependency files are maintained separately so they can be versioned, downloaded, mirrored, or packaged without editing the installer script.

To pre-download dependencies into a local wheelhouse:

```bash
python3 -m pip download -r <skill-path>/requirements/base.txt -d /path/to/wheelhouse
python3 -m pip download -r <skill-path>/requirements/docs.txt -d /path/to/wheelhouse
python3 -m pip download -r <skill-path>/requirements/multimodal.txt -d /path/to/wheelhouse
```

## Local Storage

The skill stores runtime data under:

```text
~/.local/share/local-knowledge/
  venv/
  models/
  indexes/
    <path-hash>/
      chroma/
      manifest.json
      chunks.jsonl
```

Do not store source document copies in this repository.

Implementation code is split under `scripts/core/`; keep `scripts/local_knowledge.py` as the CLI entry and keep user commands routed through `scripts/local_knowledge.sh`.

## Commands

### Check Environment

```bash
bash <skill-path>/scripts/local_knowledge.sh doctor
```

For multimodal dependency checks:

```bash
bash <skill-path>/scripts/local_knowledge.sh doctor --mode multimodal
```

### Install Dependencies

```bash
bash <skill-path>/scripts/local_knowledge.sh doctor --install
```

This creates or reuses `~/.local/share/local-knowledge/venv`.

Install multimodal dependencies only when the user explicitly wants multimodal indexing:

```bash
bash <skill-path>/scripts/local_knowledge.sh doctor --install --with-multimodal
```

### Index a Local Folder or File

```bash
bash <skill-path>/scripts/local_knowledge.sh index \
  --path /path/to/knowledge
```

The `--path` value can be a directory or a single supported file.

Safety defaults:

- `--max-file-mb 25`
- `--max-files 2000`

Default model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Default mode:

```text
text
```

### Index with a Specific Embedding Model

```bash
bash <skill-path>/scripts/local_knowledge.sh index \
  --path /path/to/knowledge \
  --model BAAI/bge-small-zh-v1.5
```

Built-in aliases:

- `default` or `en-small` -> `sentence-transformers/all-MiniLM-L6-v2`
- `zh-small` -> `BAAI/bge-small-zh-v1.5`
- `bge-m3` -> `BAAI/bge-m3`

Any other `--model` value is passed through to the backend selected for the current mode. Text mode defaults to the `sentence_transformers_text` backend.

```bash
bash <skill-path>/scripts/local_knowledge.sh index \
  --path /path/to/knowledge \
  --model /Users/me/models/my-local-embedding-model
```

### Multimodal Mode

Multimodal mode is an advanced opt-in mode. It can index supported image files alongside text chunks and keeps a separate Chroma index from text mode.

For Qwen VL embedding models, image files are passed to `SentenceTransformer.encode()` as explicit image records, using the model's sentence-transformers multimodal interface.

```bash
bash <skill-path>/scripts/local_knowledge.sh index \
  --path /path/to/knowledge \
  --mode multimodal
```

Default multimodal model:

```text
Qwen/Qwen3-VL-Embedding-2B
```

Built-in multimodal aliases:

- `qwen3-vl-2b` -> `Qwen/Qwen3-VL-Embedding-2B`

The user can specify another compatible model explicitly with `--model`. The first use may download that model:

```bash
bash <skill-path>/scripts/local_knowledge.sh index \
  --path /path/to/knowledge \
  --mode multimodal \
  --model Qwen/Qwen3-VL-Embedding-8B
```

Do not use `--mode multimodal` unless the user explicitly asks for image, screenshot, video, or multimodal retrieval. Multimodal models can be several GB and may be slow on ordinary machines.

Model maintenance rule:

- models are grouped by backend, not by model name
- compatible text embedding models use `sentence_transformers_text`
- compatible Qwen-style multimodal embedding models use `sentence_transformers_multimodal`
- add aliases and model-to-backend mappings in `scripts/core/embeddings/registry.py`
- add a new file under `scripts/core/embeddings/` only when a model needs a different loading or encoding adapter

### Search

```bash
bash <skill-path>/scripts/local_knowledge.sh search \
  --path /path/to/knowledge \
  --query "How do I deploy this project?" \
  --top-k 5
```

Add `--auto-index` to create or refresh the local index before searching when the index is missing, the selected model or chunk settings changed, source files changed, or local Chroma data is missing/corrupt:

```bash
bash <skill-path>/scripts/local_knowledge.sh search \
  --path /path/to/knowledge \
  --query "How do I deploy this project?" \
  --auto-index
```

### Ask

```bash
bash <skill-path>/scripts/local_knowledge.sh ask \
  --path /path/to/knowledge \
  --question "How do I deploy this project?"
```

`ask` returns matches and `answer: null` by default. The agent should answer the user from `matches`.

For the fastest user experience, use `--auto-index` so a user can point at a folder and ask immediately:

```bash
bash <skill-path>/scripts/local_knowledge.sh ask \
  --path /path/to/knowledge \
  --question "How do I deploy this project?" \
  --auto-index
```

### Status

```bash
bash <skill-path>/scripts/local_knowledge.sh status \
  --path /path/to/knowledge
```

### Delete a Local Index

```bash
bash <skill-path>/scripts/local_knowledge.sh delete \
  --path /path/to/knowledge \
  --yes
```

## Supported File Types

Core text support:

```text
.txt .md .markdown .json .jsonl .csv .tsv .log .yaml .yml .html .htm .xml
.py .js .jsx .ts .tsx .go .java .rs .sh .bash .zsh .css .scss .sql .toml .ini .env
```

Optional parser support when dependencies are installed:

```text
.pdf .docx .xlsx
```

Advanced multimodal support when `--mode multimodal` is used:

```text
.png .jpg .jpeg .webp .gif .bmp .tif .tiff
```

Unsupported or unreadable files are skipped and reported in output metadata.

Dependency folders, package lock files, build output directories, minified bundles, source maps, archives, and compiled binary artifacts are skipped by default.

## Output

All commands print JSON to stdout. When `--output` is omitted, the skill also tries to save the same JSON under `./out/`; if the current directory is read-only, stdout still succeeds and the save failure is reported as a warning on stderr. Passing `--output` makes that explicit output path required.

Common `search` / `ask` match shape:

```json
{
  "source": "/abs/path/knowledge/deploy.md",
  "chunk_id": "a1b2c3d4",
  "modality": "text",
  "score": 0.82,
  "line_start": 10,
  "line_end": 35,
  "text": "..."
}
```

Use returned source paths and line spans when citing context in the final answer.

## Notes

- Prefer `search` when the user wants raw local evidence.
- Prefer `ask` when the user asks a natural-language question and the calling agent should answer from retrieved context.
- Run `doctor --install` before indexing if dependencies are missing.
- Use `--auto-index` on `search` or `ask` when the user expects the skill to create or refresh the folder index automatically.
- Use `--max-file-mb` and `--max-files` when indexing very large folders.
- If the user asks for a non-default model, pass it through with `--model`.
- If the indexed model differs from the requested query model, re-index with the desired model before searching.
