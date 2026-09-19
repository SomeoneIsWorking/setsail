"""The runtime resolver must refuse loudly and must never fall back in-tree."""

from __future__ import annotations

from pathlib import Path

import pytest
from setsail.runtime import ENV_OVERRIDE, RuntimeNotFound, resolve


def _make_wiiuport(path: Path) -> Path:
    (path / "docs").mkdir(parents=True)
    (path / "docs" / "project-goals.md").write_text("x")
    (path / "tools").mkdir()
    (path / "tools" / "build_runtime.py").write_text("x")
    return path


def test_resolves_the_sibling_checkout(tmp_path: Path) -> None:
    _make_wiiuport(tmp_path / "wiiuport")
    project = tmp_path / "setsail"
    project.mkdir()
    assert resolve(project, environ={}).root == (tmp_path / "wiiuport").resolve()


def test_environment_override_wins(tmp_path: Path) -> None:
    elsewhere = _make_wiiuport(tmp_path / "elsewhere")
    _make_wiiuport(tmp_path / "wiiuport")
    project = tmp_path / "setsail"
    project.mkdir()
    resolved = resolve(project, environ={ENV_OVERRIDE: str(elsewhere)})
    assert resolved.root == elsewhere.resolve()


def test_refusal_names_every_path_tried_and_how_to_recover(tmp_path: Path) -> None:
    project = tmp_path / "setsail"
    project.mkdir()
    with pytest.raises(RuntimeNotFound) as raised:
        resolve(project, environ={ENV_OVERRIDE: str(tmp_path / "nope")})
    message = str(raised.value)
    assert str((tmp_path / "nope").resolve()) in message
    assert str((tmp_path / "wiiuport").resolve()) in message
    assert "Tried 3 location(s)" in message
    assert "git clone" in message


def test_an_incomplete_checkout_is_not_accepted(tmp_path: Path) -> None:
    """A directory that merely exists is not a runtime checkout."""
    (tmp_path / "wiiuport" / "docs").mkdir(parents=True)
    (tmp_path / "wiiuport" / "docs" / "project-goals.md").write_text("x")
    project = tmp_path / "setsail"
    project.mkdir()
    with pytest.raises(RuntimeNotFound):
        resolve(project, environ={})
