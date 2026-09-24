#!/usr/bin/env python3
"""Provision exactly as `./run.sh` does, and stop short of launching.

A maintainer's check of the fresh-clone path: it resolves the runtime
checkout, builds it, and prints the command the launcher would run, through
the launcher's own `setsail.launch.prepare`. Nothing opens on the desktop.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from setsail.launch import LaunchRefused, prepare


def main(argv: list[str]) -> int:
    try:
        command = prepare(ROOT, argv)
    except LaunchRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return refused.exit_code
    print("provisioned; ./run.sh would run: " + shlex.join(command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
