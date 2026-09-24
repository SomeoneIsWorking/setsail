#!/usr/bin/env python3
"""The player entry point: provision, build, and launch Wind Waker HD.

``run.sh`` hands control here. Discovery, build policy, and validation live in
the modules under ``tools/``; this file only composes them and presents the
result. It never runs tests, lint, or self-checks — verification is a separate
named tool.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))

from setsail.launch import LaunchRefused, prepare


def main(argv: list[str]) -> int:
    try:
        command = prepare(ROOT, argv)
    except LaunchRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return refused.exit_code
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
