import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)


def emit(data: Dict[str, Any], output: Optional[str] = None) -> None:
    text = json_dumps(data)
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"Saved JSON to {out_path}", file=sys.stderr)
    else:
        op = data.get("operation", "result")
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = Path("out") / f"local-knowledge-{op}-{ts}-{os.getpid()}.json"
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text + "\n", encoding="utf-8")
            print(f"Saved JSON to {out_path}", file=sys.stderr)
        except OSError as exc:
            print(f"Warning: could not save JSON to {out_path}: {exc}", file=sys.stderr)
    print(text)


def fail(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    sys.exit(code)
