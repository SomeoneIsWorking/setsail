"""The product is launched the way it now takes its arguments."""

from __future__ import annotations

from pathlib import Path

from setsail.runtime import RuntimeCheckout


def test_with_no_game_the_product_is_started_bare_so_it_asks() -> None:
    runtime = RuntimeCheckout(root=Path("/runtime"))
    assert runtime.launch_command(None, []) == ["/runtime/external/cemu/bin/wiiuport"]


def test_the_game_is_the_one_positional_argument_before_any_extra() -> None:
    runtime = RuntimeCheckout(root=Path("/runtime"))
    command = runtime.launch_command(Path("/games/ww.wux"), ["--fullscreen"])
    assert command == ["/runtime/external/cemu/bin/wiiuport", "/games/ww.wux", "--fullscreen"]
    assert "--game" not in command, "the product refuses the flag it no longer takes"
