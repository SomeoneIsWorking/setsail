"""Resolve the sibling wiiuport checkout that supplies the Wii U runtime.

wiiuport is consumed, never vendored. When it cannot be found, this refuses by
naming every path it tried; it never falls back to an in-tree copy or to any
other Cemu installed on the machine, because a stale copy silently winning is
exactly the failure the split exists to prevent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_OVERRIDE = "SETSAIL_WIIUPORT_DIR"
"""Maintainer override. Read here and nowhere else; see ``config`` for policy."""

SIBLING_CANDIDATES: tuple[str, ...] = ("../wiiuport", "../../wiiu/wiiuport")


class RuntimeNotFound(RuntimeError):
    """wiiuport could not be resolved; the message names every path tried."""


@dataclass(frozen=True)
class RuntimeCheckout:
    """A validated wiiuport checkout."""

    root: Path

    @property
    def build_tool(self) -> Path:
        return self.root / "tools" / "build_runtime.py"

    @property
    def emulator_binary(self) -> Path:
        """Upstream Cemu places the executable beside its runtime data root."""
        return self.root / "external" / "cemu" / "bin" / "Cemu_relwithdebinfo"


def _is_wiiuport(path: Path) -> bool:
    return (path / "docs" / "project-goals.md").is_file() and (
        path / "tools" / "build_runtime.py"
    ).is_file()


def resolve(project_root: Path, environ: dict[str, str] | None = None) -> RuntimeCheckout:
    """Return the wiiuport checkout, or refuse naming every candidate tried."""
    environ = os.environ if environ is None else environ
    tried: list[tuple[Path, str]] = []

    override = environ.get(ENV_OVERRIDE)
    if override:
        candidate = Path(override).expanduser().resolve()
        if _is_wiiuport(candidate):
            return RuntimeCheckout(root=candidate)
        tried.append((candidate, f"from {ENV_OVERRIDE}"))

    for relative in SIBLING_CANDIDATES:
        candidate = (project_root / relative).resolve()
        if _is_wiiuport(candidate):
            return RuntimeCheckout(root=candidate)
        tried.append((candidate, "sibling checkout"))

    listing = "\n".join(f"  - {path}  ({why})" for path, why in tried)
    raise RuntimeNotFound(
        "the wiiuport runtime checkout was not found. It is consumed, not "
        "vendored, so there is deliberately no in-tree copy to fall back to.\n"
        f"Tried {len(tried)} location(s):\n{listing}\n"
        "Clone it beside this project:\n"
        f"  git clone --recursive https://github.com/SomeoneIsWorking/wiiuport "
        f"{(project_root / '../wiiuport').resolve()}\n"
        f"or point {ENV_OVERRIDE} at an existing checkout.\n"
        "A checkout is recognised by docs/project-goals.md and "
        "tools/build_runtime.py."
    )
