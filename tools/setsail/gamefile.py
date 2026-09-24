"""Where the player's own Wind Waker HD disc image comes from.

The disc image is the player's. This project ships none of it and records no
path to it. The player chooses it in the runtime's own first-run setup screen,
which remembers the choice; the override here is for maintainers only, and
when it is unset the runtime asks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_GAME_PATH = "SETSAIL_GAME"
"""Maintainer override, read here and nowhere else. Never a player prerequisite."""

TITLE_ID = "0005000010143500"
"""Wind Waker HD (USA), as the runtime reads it from a disc's own metadata. The
runtime is told it on every launch and refuses a disc that holds any other
title, in its setup screen and at launch alike."""

ACCEPTED_SUFFIXES: tuple[str, ...] = (".wux", ".wud", ".iso")
"""Disc-image containers. A title installed as a directory is a separate case
and is not accepted until its identity check exists."""


class GameFileUnavailable(RuntimeError):
    """No usable disc image; the message says exactly what is missing."""


@dataclass(frozen=True)
class GameFile:
    """A path that exists and has an accepted container extension.

    This is *not* an identity check. Nothing here proves the file is Wind Waker
    HD: the runtime does, reading the disc's own metadata against `TITLE_ID`,
    because only it can decrypt the disc. The distinction is kept explicit so
    a path accepted here is never mistaken for a validated title.
    """

    path: Path

    @property
    def identity_validated(self) -> bool:
        return False


def from_environment(environ: dict[str, str] | None = None) -> GameFile | None:
    """Resolve the maintainer override, refusing with the exact reason; none
    when it is unset, so the runtime's setup screen asks the player."""
    environ = os.environ if environ is None else environ
    raw = environ.get(ENV_GAME_PATH)
    if not raw:
        return None
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
