#!/usr/bin/env python3

import argparse
from pathlib import Path

from core.commands import cmd_delete, cmd_doctor, cmd_index, cmd_search_like, cmd_status
from core.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_FILE_MB,
    DEFAULT_MAX_FILES,
    DEFAULT_MODE,
)
from core.errors import LocalKnowledgeError
from core.io_utils import fail


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", default=str(Path.home() / ".local/share/local-knowledge"))
    parser.add_argument("--venv-dir", help=argparse.SUPPRESS)
    parser.add_argument("--output")


def add_mode(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=("text", "multimodal"), default=DEFAULT_MODE)
    parser.add_argument("--backend", help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="local_knowledge.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor")
    add_common(p)
    p.add_argument("--mode", choices=("text", "multimodal"), default=DEFAULT_MODE)
    p.add_argument("--no-docs", dest="docs", action="store_false")
    p.set_defaults(docs=True)
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("index")
    add_common(p)
    add_mode(p)
    p.add_argument("--path", required=True)
    p.add_argument("--model")
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    p.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p.add_argument("--max-file-mb", type=int, default=DEFAULT_MAX_FILE_MB)
    p.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("search")
    add_common(p)
    add_mode(p)
    p.add_argument("--path", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--model")
    p.add_argument("--auto-index", action="store_true")
    p.add_argument("--chunk-size", type=int)
    p.add_argument("--chunk-overlap", type=int)
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p.add_argument("--max-file-mb", type=int)
    p.add_argument("--max-files", type=int)
    p.set_defaults(func=lambda args: cmd_search_like(args, "search"))

    p = sub.add_parser("ask")
    add_common(p)
    add_mode(p)
    p.add_argument("--path", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--model")
    p.add_argument("--auto-index", action="store_true")
    p.add_argument("--chunk-size", type=int)
    p.add_argument("--chunk-overlap", type=int)
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p.add_argument("--max-file-mb", type=int)
    p.add_argument("--max-files", type=int)
    p.set_defaults(func=lambda args: cmd_search_like(args, "ask"))

    p = sub.add_parser("status")
    add_common(p)
    add_mode(p)
    p.add_argument("--path", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("delete")
    add_common(p)
    add_mode(p)
    p.add_argument("--path", required=True)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_delete)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except LocalKnowledgeError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
