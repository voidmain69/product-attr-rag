#!/usr/bin/env python
"""Project task runner — the single entry point for dev workflows.

Usage:
    python tools/dev.py bootstrap    # create venv, install deps, install pre-commit
    python tools/dev.py check        # ruff check + format check + mypy + pytest
    python tools/dev.py fix          # ruff --fix + ruff format
    python tools/dev.py lint         # ruff check only
    python tools/dev.py typecheck    # mypy only
    python tools/dev.py test         # pytest unit tests
    python tools/dev.py test-all     # pytest including integration markers
    python tools/dev.py cov          # pytest with coverage report
    python tools/dev.py up           # docker compose up: core + monitoring profiles
    python tools/dev.py up-all       # + search profile (OpenSearch)
    python tools/dev.py down         # docker compose down
    python tools/dev.py status       # container status + health
    python tools/dev.py psql         # open psql inside the postgres container

Cross-platform (Windows/PowerShell and POSIX). No external deps beyond the
project's own dev extras.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
IS_WIN = sys.platform == "win32"
VENV_BIN = VENV / ("Scripts" if IS_WIN else "bin")


def venv_python() -> str:
    exe = VENV_BIN / ("python.exe" if IS_WIN else "python")
    return str(exe) if exe.exists() else sys.executable


def run(*cmd: str, check: bool = True) -> int:
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result.returncode


def tool(name: str) -> str:
    """Path to a console script inside the venv, falling back to bare name."""
    exe = VENV_BIN / (f"{name}.exe" if IS_WIN else name)
    return str(exe) if exe.exists() else name


def cmd_bootstrap() -> None:
    if not VENV.exists():
        run(sys.executable, "-m", "venv", str(VENV))
    py = venv_python()
    run(py, "-m", "pip", "install", "--upgrade", "pip", "-q")
    run(py, "-m", "pip", "install", "-e", ".[dev,db,queue,storage,telemetry]", "-q")
    run(py, "-m", "pre_commit", "install", check=False)
    print("bootstrap done. Activate:", VENV_BIN / ("Activate.ps1" if IS_WIN else "activate"))


def cmd_lint() -> None:
    run(tool("ruff"), "check", "src", "tests", "tools")


def cmd_fix() -> None:
    run(tool("ruff"), "check", "--fix", "src", "tests", "tools", check=False)
    run(tool("ruff"), "format", "src", "tests", "tools")


def cmd_typecheck() -> None:
    run(venv_python(), "-m", "mypy")


def cmd_test() -> None:
    run(venv_python(), "-m", "pytest", "-m", "not integration and not golden")


def cmd_test_all() -> None:
    run(venv_python(), "-m", "pytest")


def cmd_cov() -> None:
    run(
        venv_python(),
        "-m",
        "pytest",
        "-m",
        "not integration and not golden",
        "--cov",
        "--cov-report=term-missing",
    )


def cmd_check() -> None:
    run(tool("ruff"), "check", "src", "tests", "tools")
    run(tool("ruff"), "format", "--check", "src", "tests", "tools")
    cmd_typecheck()
    cmd_test()
    print("all checks passed")


def cmd_up() -> None:
    run("docker", "compose", "--profile", "core", "--profile", "monitoring", "up", "-d")
    cmd_status()


def cmd_up_all() -> None:
    run(
        "docker",
        "compose",
        "--profile",
        "core",
        "--profile",
        "monitoring",
        "--profile",
        "search",
        "up",
        "-d",
    )
    cmd_status()


def cmd_down() -> None:
    run(
        "docker",
        "compose",
        "--profile",
        "core",
        "--profile",
        "monitoring",
        "--profile",
        "search",
        "down",
    )


def cmd_status() -> None:
    run(
        "docker",
        "compose",
        "ps",
        "--format",
        "table {{.Name}}\t{{.Status}}\t{{.Ports}}",
        check=False,
    )


def cmd_psql() -> None:
    run(
        "docker",
        "compose",
        "exec",
        "postgres",
        "psql",
        "-U",
        "attrpipe",
        "-d",
        "attrpipe",
        check=False,
    )


COMMANDS = {
    "bootstrap": cmd_bootstrap,
    "check": cmd_check,
    "fix": cmd_fix,
    "lint": cmd_lint,
    "typecheck": cmd_typecheck,
    "test": cmd_test,
    "test-all": cmd_test_all,
    "cov": cmd_cov,
    "up": cmd_up,
    "up-all": cmd_up_all,
    "down": cmd_down,
    "status": cmd_status,
    "psql": cmd_psql,
}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
