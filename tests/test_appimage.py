"""The player's package: what it bundles, what it refuses, and what it names."""

from __future__ import annotations

import hashlib
import struct
import subprocess
import zlib
from collections.abc import Sequence
from pathlib import Path

import pytest
from setsail import appimage
from setsail.appimage import PackageRefused
from setsail.gamefile import TITLE_ID

LDD_OUTPUT = """\
\tlinux-vdso.so.1 (0x00007ffc5a1f2000)
\tlibbluetooth.so.3 => /lib64/libbluetooth.so.3 (0x00007f0e4c000000)
\tlibstdc++.so.6 => /lib64/libstdc++.so.6 (0x00007f0e4bc00000)
\tlibc.so.6 => /lib64/libc.so.6 (0x00007f0e4b800000)
\t/lib64/ld-linux-x86-64.so.2 (0x00007f0e4c200000)
"""


def test_ldd_output_is_read_into_every_library() -> None:
    libraries = appimage.parse_ldd(LDD_OUTPUT)
    assert [library.name for library in libraries] == [
        "linux-vdso.so.1",
        "libbluetooth.so.3",
        "libstdc++.so.6",
        "libc.so.6",
        "ld-linux-x86-64.so.2",
    ]
    assert libraries[1].path == Path("/lib64/libbluetooth.so.3")


def test_only_what_a_desktop_cannot_be_assumed_to_have_is_bundled() -> None:
    bundled = appimage.libraries_to_bundle(appimage.parse_ldd(LDD_OUTPUT))
    assert [library.name for library in bundled] == ["libbluetooth.so.3", "libstdc++.so.6"]


@pytest.mark.parametrize(
    ("output", "reason"),
    [
        ("\tlibmissing.so.1 => not found\n", "not installed"),
        ("\tstatically linked, somehow\n", "cannot read"),
        ("\n\n", "no libraries"),
    ],
)
def test_ldd_output_that_would_ship_a_broken_package_is_refused(output: str, reason: str) -> None:
    with pytest.raises(PackageRefused, match=reason):
        appimage.parse_ldd(output)


def test_the_glibc_floor_is_the_newest_version_named() -> None:
    symbols = "memcpy GLIBC_2.14\nfoo GLIBC_2.43\nbar GLIBC_2.2.5\nbaz GLIBC_2.9\n"
    assert appimage.glibc_floor(symbols) == "2.43"
    with pytest.raises(PackageRefused):
        appimage.glibc_floor("no versions here")


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


def test_an_executable_naming_where_it_was_built_is_refused(tmp_path: Path) -> None:
    checkout = Path("/builds/maintainer/wiiuport")
    binary = tmp_path / "wiiuport"
    binary.write_bytes(b"\x7fELF...wiiuport/src/Main.cpp\x00assert failed\x00")
    appimage.refuse_build_paths(binary, (checkout,))
    binary.write_bytes(b"\x7fELF.../builds/maintainer/wiiuport/src/Main.cpp\x00")
    with pytest.raises(PackageRefused, match="names /builds/maintainer/wiiuport 1 times"):
        appimage.refuse_build_paths(binary, (checkout,))
