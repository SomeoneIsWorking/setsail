"""The disc-image source refuses precisely, and never claims identity."""

from __future__ import annotations

from pathlib import Path

import pytest
from setsail.gamefile import ENV_GAME_PATH, GameFileUnavailable, from_environment


def test_unset_override_leaves_the_choice_to_the_runtimes_setup_screen() -> None:
    assert from_environment(environ={}) is None


def test_nonexistent_path_is_refused_by_name(tmp_path: Path) -> None:
    missing = tmp_path / "absent.wux"
    with pytest.raises(GameFileUnavailable, match="not an existing file"):
        from_environment(environ={ENV_GAME_PATH: str(missing)})


def test_wrong_container_is_refused(tmp_path: Path) -> None:
    other = tmp_path / "notes.txt"
    other.write_text("x")
    with pytest.raises(GameFileUnavailable, match="not one of"):
        from_environment(environ={ENV_GAME_PATH: str(other)})


def test_accepted_container_resolves_but_does_not_claim_identity(tmp_path: Path) -> None:
    image = tmp_path / "game.wux"
    image.write_bytes(b"\x00")
    resolved = from_environment(environ={ENV_GAME_PATH: str(image)})
    assert resolved.path == image
    assert resolved.identity_validated is False, (
        "an accepted extension must never be mistaken for a validated title"
    )
