"""Everything a launch needs before the product starts, in one owner.

The player's launcher (`bootstrap.py`) and the maintainer's provisioning check
(`tools/provision.py`) both come through here, so the check proves the path a
player takes rather than a copy of it: resolve the runtime checkout, read the
maintainer's disc-image override, bring the runtime's build up to date, and
return the command that starts the product.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from setsail.gamefile import GameFileUnavailable, from_environment
from setsail.runtime import RuntimeNotFound, resolve


class LaunchRefused(RuntimeError):
    """The product cannot be started; the message says why. `exit_code` is
    2 for what the person must change and 1 for a failed build."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def prepare(project_root: Path, argv: list[str]) -> list[str]:
    """The command that starts the product, with its runtime built."""
    try:
        runtime = resolve(project_root)
    except RuntimeNotFound as error:
        raise LaunchRefused(str(error), 2) from error
    try:
        game = from_environment()
    except GameFileUnavailable as error:
        raise LaunchRefused(str(error), 2) from error

    # Always brought up to date, not only when absent: a runtime checkout
    # pulled since the last build would otherwise launch the older binary.
    # An up-to-date build is a few seconds of checking.
    print(
        f"bringing the runtime in {runtime.root} up to date (the first build takes a while)",
        flush=True,
    )
    built = subprocess.run(
        ["uv", "run", "--frozen", "python", str(runtime.build_tool)],
        cwd=runtime.root,
        check=False,
    )
    if built.returncode != 0:
        raise LaunchRefused(
            "building the runtime failed; its output is above. "
            "Not launching the build that was there before.",
            1,
        )
    if not runtime.product_binary.is_file():
        raise LaunchRefused(
            f"the runtime reported success but {runtime.product_binary} does not exist; "
            "refusing to launch a stale or absent build",
            1,
        )
    return runtime.launch_command(None if game is None else game.path, argv)
