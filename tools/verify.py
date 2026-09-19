#!/usr/bin/env python3
"""Run every gate. Verification never routes through run.sh."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from setsail.verify import run_all


def main() -> int:
    results = run_all(ROOT)
    for result in results:
        print(result.render())
        print()
    failed = [r.name for r in results if not r.passed]
    print(f"{len(results) - len(failed)} of {len(results)} gates passed")
    if failed:
        print("failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
