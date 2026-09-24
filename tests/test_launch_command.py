"""The product is launched the way it now takes its arguments."""

from __future__ import annotations

from pathlib import Path

from setsail.gamefile import TITLE_ID
from setsail.runtime import RuntimeCheckout


def test_with_no_game_the_product_is_started_bare_so_it_asks() -> None:
    runtime = RuntimeCheckout(root=Path("/runtime"))
    assert runtime.launch_command(None, []) == [
        "/runtime/external/cemu/bin/wiiuport",
        "--title-id",
        TITLE_ID,
    ]


def test_the_game_is_the_one_positional_argument_before_any_extra() -> None:
    runtime = RuntimeCheckout(root=Path("/runtime"))
    command = runtime.launch_command(Path("/games/ww.wux"), ["--fullscreen"])
    assert command == [
        "/runtime/external/cemu/bin/wiiuport",
        "--title-id",
        TITLE_ID,
        "/games/ww.wux",
        "--fullscreen",
    ]
    assert "--game" not in command, "the product refuses the flag it no longer takes"


def test_the_runtime_is_always_told_which_title_this_product_runs() -> None:
    runtime = RuntimeCheckout(root=Path("/runtime"))
    for game, extra in ((None, []), (Path("/games/ww.wux"), ["--hidden"])):
        command = runtime.launch_command(game, extra)
        assert command[1:3] == ["--title-id", "0005000010143500"]
