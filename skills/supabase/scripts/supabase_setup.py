#!/usr/bin/env python3
"""Find, automatically install and check the Supabase CLI."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True


def frevana_bin_dir():
    return Path(os.environ.get("FREVANA_BIN_DIR",
                               str(Path.home() / ".frevana/bin"))).expanduser().resolve()


def executable(path):
    if not path.is_file():
        return False
    if os.name == "nt":
        return path.suffix.lower() in (".exe", ".cmd", ".bat", "") and path.stat().st_size > 0
    return os.access(path, os.X_OK)


def link_frevana_bin(binary):
    """Expose a newly installed CLI without replacing any existing user entry."""
    try:
        bin_dir = frevana_bin_dir()
        bin_dir.mkdir(parents=True, exist_ok=True)
        target = Path(binary).resolve()
        # Exclusive creation also preserves existing files and dangling symlinks.
        # Windows symlinks may need Administrator privileges; use a .cmd shim.
        if os.name == "nt":
            cmd_shim = bin_dir / "supabase.cmd"
            with cmd_shim.open("x", encoding="utf-8", newline="") as stream:
                stream.write(f'@echo off\r\n"{target}" %*\r\n')
        else:
            (bin_dir / "supabase").symlink_to(target)
    except FileExistsError:
        # The installed binary is still used directly for this operation.
        return
    except OSError as error:
        print(f"WARNING: Could not create the optional Supabase launcher ({error.strerror}); "
              "using the installed CLI directly.", file=sys.stderr)


def resolve_global_npm_supabase(npm):
    installed = shutil.which("supabase")
    if installed and executable(Path(installed)):
        return Path(installed)
    result = subprocess.run([npm, "prefix", "-g"], capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and result.stdout.strip():
        prefix = Path(result.stdout.strip())
        for rel in (
            "bin/supabase",
            "bin/supabase.cmd",
            "bin/supabase.exe",
            "bin/supabase.bat",
            "supabase.cmd",
            "supabase.exe",
            "supabase.bat",
            "supabase",
        ):
            candidate = prefix / rel
            if executable(candidate):
                return candidate
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            npm_dir = Path(appdata) / "npm"
            for rel in ("supabase.cmd", "supabase.exe", "supabase.bat", "supabase"):
                candidate = npm_dir / rel
                if executable(candidate):
                    return candidate
    return None


def verify_installed_cli(binary, workdir):
    result = subprocess.run([str(binary), "--version"], cwd=workdir,
                            capture_output=True, text=True, timeout=30)
    if result.returncode or not result.stdout.strip():
        raise ValueError("Supabase was installed but its version check failed; no operation was run.")
    link_frevana_bin(binary)
    return str(binary)


def install_cli(workdir):
    npm, node = shutil.which("npm"), shutil.which("node")
    brew = shutil.which("brew")
    scoop = shutil.which("scoop")
    winget = shutil.which("winget")
    node_ready = False
    if npm and node:
        result = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30)
        try:
            node_ready = result.returncode == 0 and int(result.stdout.strip().lstrip("v").split(".")[0]) >= 20
        except ValueError:
            pass
    if node_ready:
        command = [npm, "install", "-g", "--no-audit", "--no-fund", "supabase@latest"]
        print("Supabase CLI missing; installing official npm package globally (npm install -g).", file=sys.stderr)
        binary = None
    elif scoop:
        command = [scoop, "install", "supabase"]
        print("Supabase CLI missing; installing with Scoop.", file=sys.stderr)
        binary = None
    elif winget:
        command = [winget, "install", "--id=Supabase.CLI", "-e", "--accept-source-agreements", "--accept-package-agreements"]
        print("Supabase CLI missing; installing with Winget.", file=sys.stderr)
        binary = None
    elif brew:
        command = [brew, "install", "supabase/tap/supabase"]
        print("Supabase CLI missing; installing with Homebrew.", file=sys.stderr)
        binary = None
    else:
        raise ValueError("Cannot auto-install Supabase: need npm with Node.js 20+, Scoop, Winget, or Homebrew. "
                         "Install an official package manager/runtime and retry.")
    # Keep installer chatter out of structured stdout; one bounded install attempt.
    result = subprocess.run(command, cwd=workdir, stdout=sys.stderr, timeout=300)
    if result.returncode:
        raise ValueError("Supabase CLI installation failed; no operation was run. "
                         "Resolve the installer/network/permission error before retrying.")
    if node_ready:
        binary = resolve_global_npm_supabase(npm)
        if binary is None:
            raise ValueError("Installer finished without a usable Supabase binary; no operation was run.")
    elif command[0] == brew:
        result = subprocess.run([brew, "--prefix", "supabase"], capture_output=True,
                                text=True, timeout=30)
        if result.returncode or not result.stdout.strip():
            raise ValueError("Homebrew installation finished but its Supabase prefix could not be resolved.")
        binary = Path(result.stdout.strip()) / "bin/supabase"
    else:
        installed = shutil.which("supabase")
        binary = Path(installed) if installed else None
    if not binary or not executable(binary):
        raise ValueError("Installer finished without a usable Supabase binary; no operation was run.")
    return verify_installed_cli(binary, workdir)


def cli_path(workdir, auto_install=True):
    for directory in (workdir, *workdir.parents):
        for name in ("supabase", "supabase.cmd", "supabase.exe", "supabase.bat"):
            candidate = directory / f"node_modules/.bin/{name}"
            if executable(candidate):
                return str(candidate)
    installed = shutil.which("supabase")
    if installed:
        return installed
    bin_dir = frevana_bin_dir()
    for name in ("supabase", "supabase.cmd", "supabase.exe", "supabase.bat"):
        frevana_link = bin_dir / name
        if executable(frevana_link):
            return str(frevana_link)
    if not auto_install:
        raise ValueError("Supabase CLI not found; automatic installation disabled by --no-install.")
    return install_cli(workdir)


COMMANDS = ("check",)


def handle(args, base, workdir, output, native):
    from supabase_common import emit

    result = subprocess.run(base + ["--version"], cwd=workdir, capture_output=True, text=True)
    if result.returncode:
        print("ERROR: Supabase CLI version check failed; no working CLI verified.", file=sys.stderr)
        return result.returncode
    emit({"status": "ok", "installed": True, "version": result.stdout.strip(), "path": base[0]})
    return 0


def main(argv=None):
    from supabase_common import run
    return run(COMMANDS, __doc__, handle, argv)


if __name__ == "__main__":
    from supabase_common import entrypoint
    entrypoint(main)
