#!/usr/bin/env python3
"""Run the Sensor Tower CLI and bootstrap future Python dependencies."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = SKILL_ROOT / "requirements.txt"
CLI = SKILL_ROOT / "scripts" / "sensortower.py"


def has_dependencies(content: str) -> bool:
    """Return whether a requirements file contains an active entry."""
    return any(
        line.strip() and not line.lstrip().startswith("#")
        for line in content.splitlines()
    )


def cache_root() -> Path:
    configured = os.environ.get("SENSORTOWER_SKILL_CACHE")
    if configured:
        return Path(configured).expanduser()
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache).expanduser() if xdg_cache else Path.home() / ".cache"
    return base / "frevana-skills" / "sensortower"


def venv_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def ensure_runtime(
    requirements: Path = REQUIREMENTS,
    *,
    runtime_cache: Path | None = None,
) -> Path:
    try:
        content = requirements.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"cannot read {requirements}: {exc}") from exc

    if not has_dependencies(content):
        return Path(sys.executable)

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    environment = (runtime_cache or cache_root()) / f"py{sys.version_info.major}{sys.version_info.minor}-{digest}"
    python = venv_python(environment)
    ready = environment / ".ready"
    if ready.is_file() and python.is_file():
        return python

    try:
        environment.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(environment)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--require-hashes",
                "--requirement",
                str(requirements),
            ],
            check=True,
        )
        ready.write_text("ok\n", encoding="utf-8")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "automatic dependency installation failed; check Python, pip, "
            "network access, and SENSORTOWER_SKILL_CACHE permissions"
        ) from exc
    return python


def main() -> int:
    try:
        python = ensure_runtime()
        completed = subprocess.run([str(python), str(CLI), *sys.argv[1:]])
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: unable to start Sensor Tower CLI: {exc}", file=sys.stderr)
        return 1
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
