#!/usr/bin/env python3
"""Deterministic JSON helpers for verbatim WordPress content writes."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any


def load_object(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON object from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def required_content(value: dict[str, Any], path: str) -> str:
    content = value.get("content")
    if not isinstance(content, str):
        raise ValueError(f"{path} must contain a top-level string field named content")
    return content


def command_has_content(args: argparse.Namespace) -> int:
    value = load_object(args.input)
    if "content" not in value:
        return 1
    required_content(value, args.input)
    return 0


def command_extract_id(args: argparse.Namespace) -> int:
    value = load_object(args.response)
    object_id = value.get("id")
    if (
        not isinstance(object_id, int)
        or isinstance(object_id, bool)
        or object_id <= 0
    ):
        raise ValueError(f"{args.response} does not contain a positive integer id")
    print(object_id)
    return 0


def command_compare(args: argparse.Namespace) -> int:
    source = required_content(load_object(args.source), args.source)
    response = load_object(args.response)
    content = response.get("content")
    actual = content.get("raw") if isinstance(content, dict) else None
    if not isinstance(actual, str):
        raise ValueError(f"{args.response} does not contain content.raw")
    if source == actual:
        print("content_match=true", file=sys.stderr)
        return 0

    print("content_match=false", file=sys.stderr)
    print(
        f"submitted_characters={len(source)} wordpress_characters={len(actual)}",
        file=sys.stderr,
    )
    diff = difflib.unified_diff(
        source.splitlines(),
        actual.splitlines(),
        fromfile="submitted-content",
        tofile="wordpress-content.raw",
        n=2,
        lineterm="",
    )
    for index, line in enumerate(diff):
        if index >= 80:
            print("... diff truncated ...", file=sys.stderr)
            break
        print(line, file=sys.stderr)
    return 3


def command_verify_status(args: argparse.Namespace) -> int:
    source = load_object(args.source)
    expected = source.get("status")
    if expected is None:
        return 0
    if not isinstance(expected, str) or not expected:
        raise ValueError(f"{args.source} contains an invalid status")

    response = load_object(args.response)
    actual = response.get("status")
    if actual != expected:
        print(
            f"status_match=false expected_status={expected} wordpress_status={actual}",
            file=sys.stderr,
        )
        return 4
    print("status_match=true", file=sys.stderr)
    return 0


def command_same_path(args: argparse.Namespace) -> int:
    first = Path(args.first).expanduser().resolve(strict=False)
    second = Path(args.second).expanduser().resolve(strict=False)
    return 0 if first == second else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    has_content = subparsers.add_parser("has-content")
    has_content.add_argument("input")
    has_content.set_defaults(handler=command_has_content)

    extract_id = subparsers.add_parser("extract-id")
    extract_id.add_argument("response")
    extract_id.set_defaults(handler=command_extract_id)

    compare = subparsers.add_parser("compare")
    compare.add_argument("source")
    compare.add_argument("response")
    compare.set_defaults(handler=command_compare)

    verify_status = subparsers.add_parser("verify-status")
    verify_status.add_argument("source")
    verify_status.add_argument("response")
    verify_status.set_defaults(handler=command_verify_status)

    same_path = subparsers.add_parser("same-path")
    same_path.add_argument("first")
    same_path.add_argument("second")
    same_path.set_defaults(handler=command_same_path)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
