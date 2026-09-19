"""Where the player's own Wind Waker HD disc image comes from.

The disc image is the player's. This project ships none of it and records no
path to it. Until the first-run setup screen exists (state item ST-SETUP), the
only source is a maintainer override, and its absence is an explicit refusal
that says so rather than a silent failure to launch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_GAME_PATH = "SETSAIL_GAME"
"""Maintainer override, read here and nowhere else. Never a player prerequisite."""

ACCEPTED_SUFFIXES: tuple[str, ...] = (".wux", ".wud", ".iso")
"""Disc-image containers. A title installed as a directory is a separate case
and is not accepted until its identity check exists."""


class GameFileUnavailable(RuntimeError):
    """No usable disc image; the message says exactly what is missing."""


@dataclass(frozen=True)
class GameFile:
    """A path that exists and has an accepted container extension.

    This is *not* an identity check. Nothing here proves the file is Wind Waker
    HD; that is state item ST-IDENT and needs the runtime's meta/meta.xml
    reader. The distinction is kept explicit so a launch cannot later be
    mistaken for evidence that identity was validated.
    """

    path: Path

    @property
    def identity_validated(self) -> bool:
        return False


def from_environment(environ: dict[str, str] | None = None) -> GameFile:
    """Resolve the maintainer override, refusing with the exact reason."""
    environ = os.environ if environ is None else environ
    raw = environ.get(ENV_GAME_PATH)
    if not raw:
        raise GameFileUnavailable(
            "no Wind Waker HD disc image is configured.\n"
            "The first-run setup screen that would ask you for one is not built "
            "yet (see ST-SETUP in docs/project-state.md), so for now a "
            f"maintainer sets {ENV_GAME_PATH} to the path of their own copy:\n"
            f"  {ENV_GAME_PATH}=/path/to/your/wind-waker-hd.wux ./run.sh\n"
            f"Accepted containers: {', '.join(ACCEPTED_SUFFIXES)}"
        )
    path = Path(raw).expanduser()
    if not path.is_file():
        raise GameFileUnavailable(
            f"{ENV_GAME_PATH} points at {path}, which is not an existing file"
        )
    if path.suffix.lower() not in ACCEPTED_SUFFIXES:
        raise GameFileUnavailable(
            f"{ENV_GAME_PATH} points at {path}, whose extension "
            f"{path.suffix!r} is not one of {', '.join(ACCEPTED_SUFFIXES)}"
        )
    return GameFile(path=path)
