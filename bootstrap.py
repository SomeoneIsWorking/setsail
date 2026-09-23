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

from setsail.gamefile import GameFileUnavailable, from_environment
from setsail.runtime import RuntimeNotFound, resolve


def main(argv: list[str]) -> int:
    try:
        runtime = resolve(ROOT)
    except RuntimeNotFound as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2

    try:
        game = from_environment()
    except GameFileUnavailable as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2

    if not runtime.product_binary.is_file():
        print(f"building the runtime in {runtime.root} (first run takes a while)")
        built = subprocess.run(
            ["uv", "run", "--frozen", "python", str(runtime.build_tool)],
            cwd=runtime.root, check=False,
        )
        if built.returncode != 0:
            print(
                "refused: building the runtime failed; its output is above.",
                file=sys.stderr,
            )
            return 1
    if not runtime.product_binary.is_file():
        print(
            f"refused: the runtime reported success but {runtime.product_binary} "
            "does not exist; refusing to launch a stale or absent build",
            file=sys.stderr,
        )
        return 1

    command = runtime.launch_command(None if game is None else game.path, argv)
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
