#!/usr/bin/env python
"""Claude Code PostToolUse hook: auto-fix + format Python files after Edit/Write.

Reads the hook payload from stdin, and if the touched file is a .py inside the
repo, runs `ruff check --fix` and `ruff format` on it. Exit code 0 always —
formatting problems must never block the agent; CI is the enforcement gate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def find_ruff() -> str | None:
    venv_ruff = (
        ROOT
        / ".venv"
        / ("Scripts" if sys.platform == "win32" else "bin")
        / ("ruff.exe" if sys.platform == "win32" else "ruff")
    )
    if venv_ruff.exists():
        return str(venv_ruff)
    return shutil.which("ruff")


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".py"):
        return
    path = Path(file_path)
    if not path.exists() or ROOT not in path.resolve().parents:
        return
    ruff = find_ruff()
    if not ruff:
        return
    subprocess.run([ruff, "check", "--fix", "--quiet", str(path)], check=False)
    subprocess.run([ruff, "format", "--quiet", str(path)], check=False)


if __name__ == "__main__":
    main()
