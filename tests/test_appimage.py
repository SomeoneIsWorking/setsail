"""The player's package: what it bundles, what it refuses, and what it names."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import zlib
from collections.abc import Sequence
from pathlib import Path

import pytest
from setsail import appimage
from setsail.appimage import PackageRefused
from setsail.gamefile import TITLE_ID


def test_the_type2_runtime_is_refused_unless_it_is_the_pinned_one(tmp_path: Path) -> None:
    fetched: list[str] = []

    def download(url: str, into: Path) -> None:
        fetched.append(url)
        into.write_bytes(b"not the pinned runtime")

    cache = tmp_path / "cache" / "runtime-x86_64"
    with pytest.raises(PackageRefused, match="not the pinned"):
        appimage.verified_type2_runtime(cache, download)
    assert fetched == [appimage.TYPE2_RUNTIME_URL]
    assert hashlib.sha256(cache.read_bytes()).hexdigest() != appimage.TYPE2_RUNTIME_SHA256


def test_the_launcher_names_this_product_and_title_ahead_of_the_players_arguments() -> None:
    command = appimage.APP_RUN.splitlines()[-1]
    fixed = f'--product-name "{appimage.PRODUCT_NAME}" --title-id {TITLE_ID}'
    assert fixed in command
    assert command.index(fixed) < command.index('"$@"')


def test_the_icon_is_a_well_formed_png() -> None:
    icon = appimage.icon_png(32)
    assert icon.startswith(b"\x89PNG\r\n\x1a\n")
    length, kind = struct.unpack(">I4s", icon[8:16])
    width, height = struct.unpack(">II", icon[16:24])
    assert (kind, length, width, height) == (b"IHDR", 13, 32, 32)
    assert struct.unpack(">I", icon[29:33])[0] == zlib.crc32(icon[12:29])


def _answer(returncode: int, stderr: str) -> appimage.Runner:
    def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(command), returncode, "", stderr)

    return run


def test_a_package_that_refuses_another_title_as_the_runtime_does_passes() -> None:
    refusal = f"{appimage.PRODUCT_NAME} runs {TITLE_ID}, not {appimage.ANOTHER_TITLE_ID}"
    assert appimage.check_package(Path("pkg"), _answer(2, refusal)) == refusal


@pytest.mark.parametrize(
    ("returncode", "stderr"),
    [
        (0, ""),
        (127, "error while loading shared libraries: libstdc++.so.6"),
        (2, f"wiiuport runs {TITLE_ID}, not {appimage.ANOTHER_TITLE_ID}"),
    ],
)
def test_a_package_that_does_not_start_as_this_product_is_refused(
    returncode: int, stderr: str
) -> None:
    with pytest.raises(PackageRefused):
        appimage.check_package(Path("pkg"), _answer(returncode, stderr))


def test_a_package_that_reports_no_display_and_exits_passes(tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        seen.append(list(command))
        return subprocess.CompletedProcess(
            list(command), 1, "", "[shell:error] the setup screen would not open: no video"
        )

    appimage.check_exit(Path("pkg"), tmp_path, run)
    assert f"SDL_VIDEO_DRIVER={appimage.NO_VIDEO_DRIVER}" in seen[0]
    assert f"XDG_CONFIG_HOME={tmp_path / 'config'}" in seen[0]
    assert seen[0][-1] == "pkg"


@pytest.mark.parametrize(
    ("returncode", "stderr"),
    [
        (134, "the setup screen would not open\nterminate called without an active exception"),
        (1, "the setup screen would not open\nterminate called\nError: signal 6:\nAborted!"),
        (124, "the setup screen would not open"),
        (0, "the setup screen would not open"),
        (1, "the Vulkan loader would not initialise"),
    ],
)
def test_a_package_that_aborts_hangs_or_fails_otherwise_on_leaving_is_refused(
    tmp_path: Path, returncode: int, stderr: str
) -> None:
    with pytest.raises(PackageRefused):
        appimage.check_exit(Path("pkg"), tmp_path, _answer(returncode, stderr))


def _bundle(root: Path, executable: str = "usr/bin/wiiuport") -> Path:
    (root / "usr" / "bin").mkdir(parents=True)
    (root / "usr" / "lib").mkdir()
    (root / "usr" / "bin" / "wiiuport").write_bytes(b"ELF")
    (root / "usr" / "lib" / "libstdc++.so.6").write_bytes(b"lib")
    manifest = {
        "executable": executable,
        "libraries": "usr/lib",
        "glibc_floor": "2.39",
        "bundled": ["libstdc++.so.6"],
        "linked": 20,
    }
    (root / "runtime.json").write_text(json.dumps(manifest))
    return root


def test_the_appdir_is_the_runtimes_bundle_made_this_product(tmp_path: Path) -> None:
    appdir = tmp_path / "AppDir"
    manifest = appimage.stage(appdir, _bundle(tmp_path / "bundle"))
    assert manifest["glibc_floor"] == "2.39"
    assert (appdir / "usr" / "bin" / "wiiuport").read_bytes() == b"ELF"
    assert (appdir / "usr" / "lib" / "libstdc++.so.6").is_file()
    assert (appdir / "AppRun").read_text() == appimage.APP_RUN
    assert f"Name={appimage.PRODUCT_NAME}" in (appdir / "setsail.desktop").read_text()


def test_a_directory_that_is_not_the_bundle_the_launcher_expects_is_refused(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(PackageRefused, match="not a staged runtime bundle"):
        appimage.stage(tmp_path / "one", empty)
    moved = _bundle(tmp_path / "moved", executable="bin/wiiuport")
    with pytest.raises(PackageRefused, match="puts its executable"):
        appimage.stage(tmp_path / "two", moved)
