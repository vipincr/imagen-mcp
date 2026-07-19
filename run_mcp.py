#!/usr/bin/env python3
"""Self-bootstrapping launcher for the Imagen MCP server.

This is the recommended command for MCP clients such as Claude Desktop and
Claude Code. Point the client at::

    python3 /absolute/path/to/imagen-mcp/run_mcp.py

On first launch it creates a private virtual environment (default
``~/.imagen-mcp/venv``), installs this package and its dependencies, and then
hands off to the server. Subsequent launches reuse the environment and start
almost instantly, so the client can spawn the server on demand.

Design notes
------------
* The MCP stdio protocol uses **stdout** for JSON-RPC. Every diagnostic and all
  ``pip`` output is therefore routed to **stderr** so it can never corrupt the
  protocol stream.
* The final step replaces this process (``os.execv``) with the venv Python
  running ``python -m imagen_mcp``, so there is no wrapper process sitting on
  the pipe.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def log(message: str) -> None:
    """Write a diagnostic line to stderr (never stdout)."""
    print(f"[imagen-mcp] {message}", file=sys.stderr, flush=True)


def home_dir() -> Path:
    override = os.environ.get("IMAGEN_MCP_HOME")
    base = Path(override).expanduser() if override else Path.home() / ".imagen-mcp"
    return base


def venv_dir() -> Path:
    return home_dir() / "venv"


def venv_python(vdir: Path) -> Path:
    if os.name == "nt":
        return vdir / "Scripts" / "python.exe"
    return vdir / "bin" / "python"


def package_version() -> str:
    """Read __version__ from the package without importing it (deps may be absent)."""
    init_file = REPO_ROOT / "imagen_mcp" / "__init__.py"
    try:
        text = init_file.read_text(encoding="utf-8")
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
    except OSError:
        pass
    return "0"


def marker_path(vdir: Path) -> Path:
    return vdir / ".installed"


def is_ready(vdir: Path, version: str) -> bool:
    py = venv_python(vdir)
    if not py.exists():
        return False
    marker = marker_path(vdir)
    if not marker.exists():
        return False
    try:
        return marker.read_text(encoding="utf-8").strip() == version
    except OSError:
        return False


def run(cmd: list[str]) -> None:
    """Run a subprocess, routing all of its output to stderr."""
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True, stdout=sys.stderr, stderr=sys.stderr)


def ensure_environment() -> Path:
    vdir = venv_dir()
    version = package_version()

    if is_ready(vdir, version):
        return venv_python(vdir)

    home_dir().mkdir(parents=True, exist_ok=True)
    py = venv_python(vdir)

    if not py.exists():
        log(f"Creating virtual environment at {vdir} …")
        venv.EnvBuilder(with_pip=True, clear=False, upgrade=False).create(str(vdir))

    log("Installing/updating imagen-mcp and dependencies (first run only) …")
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    # Editable install so the venv tracks this checkout.
    run([str(py), "-m", "pip", "install", "--editable", str(REPO_ROOT)])

    marker_path(vdir).write_text(version, encoding="utf-8")
    log("Environment ready.")
    return py


def main() -> None:
    try:
        py = ensure_environment()
    except subprocess.CalledProcessError as exc:
        log(f"Setup failed: {exc}. Ensure Python 3 and network access are available.")
        sys.exit(1)
    except OSError as exc:
        log(f"Setup failed: {exc}")
        sys.exit(1)

    # Replace this process with the server so stdio is a clean pipe.
    args = [str(py), "-m", "imagen_mcp"]
    log("Starting server …")
    os.execv(str(py), args)


if __name__ == "__main__":
    main()
