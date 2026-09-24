"""The launcher's refusals, and the order they fire in.

These are paths a person meets before anything works, so they are tested
rather than assumed.

The "no runtime checkout at all" case is deliberately **not** tested here. The
resolver tries the environment override first and then sibling directories, so
on a developer machine -- where a real `../wiiuport` exists -- pointing the
override at an absent path correctly still resolves the sibling. Making the
case reachable would mean copying the project to an isolated tree, which tests
the copy rather than the checkout. It is covered instead by the resolver's own
unit tests in `test_runtime_resolver.py`, and end to end by the CI job, where
no sibling exists.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _launch(env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("SETSAIL_GAME", None)
    env.pop("SETSAIL_WIIUPORT_DIR", None)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(ROOT / "bootstrap.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _fake_runtime(at: Path) -> Path:
    (at / "docs").mkdir(parents=True)
    (at / "docs" / "project-goals.md").write_text("x")
    (at / "tools").mkdir()
    (at / "tools" / "build_runtime.py").write_text("x")
    return at


def test_no_disc_image_goes_on_to_the_runtime_which_asks_for_one(tmp_path: Path) -> None:
    """With nothing configured the launcher is not the one to refuse: the
    runtime's setup screen asks the player. Here the fake runtime is unbuilt,
    so the launcher gets as far as building it."""
    runtime = _fake_runtime(tmp_path / "wiiuport")
    result = _launch({"SETSAIL_WIIUPORT_DIR": str(runtime)})
    assert "building the runtime" in result.stdout
    assert "SETSAIL_GAME" not in result.stderr


def test_a_path_with_the_wrong_container_is_refused(tmp_path: Path) -> None:
    runtime = _fake_runtime(tmp_path / "wiiuport")
    wrong = tmp_path / "not-a-disc-image.txt"
    wrong.write_text("x")
    result = _launch({"SETSAIL_WIIUPORT_DIR": str(runtime), "SETSAIL_GAME": str(wrong)})
    assert result.returncode == 2
    assert "not one of" in result.stderr


def test_a_missing_disc_image_is_refused_by_name(tmp_path: Path) -> None:
    runtime = _fake_runtime(tmp_path / "wiiuport")
    absent = tmp_path / "absent.wux"
    result = _launch({"SETSAIL_WIIUPORT_DIR": str(runtime), "SETSAIL_GAME": str(absent)})
    assert result.returncode == 2
    assert "not an existing file" in result.stderr
    assert str(absent) in result.stderr
    assert "building the runtime" not in result.stdout, (
        "a bad override must be refused before a build is started"
    )
