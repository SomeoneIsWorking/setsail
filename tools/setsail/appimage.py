"""The player's package: an asset-free AppImage of the runtime, made for this title.

The AppImage holds the runtime's executable and the data it reads beside it,
the libraries a desktop cannot be assumed to have, and a launcher that always
names this title. It holds no game files, keys or anything derived from them:
the player chooses their own disc image on the runtime's first-run screen.

Built on the maintainer's host, so the package needs a glibc at least as new as
the one it was built against; that floor is reported, never hidden.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import struct
import subprocess
import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from setsail.gamefile import TITLE_ID
from setsail.runtime import RuntimeCheckout

APP_NAME = "setsail"
PRODUCT_NAME = "Set Sail"
"""What the player sees the product called, on its window and first-run screen."""

TYPE2_RUNTIME_URL = (
    "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64"
)
TYPE2_RUNTIME_SHA256 = "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"
"""The AppImage runtime prepended to the image, pinned by release and checksum."""

HOST_PROVIDED: frozenset[str] = frozenset(
    {
        # The C library and its loader: the one thing an AppImage must take from the host.
        "linux-vdso.so.1",
        "ld-linux-x86-64.so.2",
        "libc.so.6",
        "libm.so.6",
        "libgcc_s.so.1",
        # The display, input and font stack every desktop session already runs; a
        # bundled copy can disagree with the host's server or drivers.
        "libX11.so.6",
        "libxcb.so.1",
        "libXau.so.6",
        "libXrender.so.1",
        "libwayland-client.so.0",
        "libffi.so.8",
        "libudev.so.1",
        "libfreetype.so.6",
        "libharfbuzz.so.0",
        "libgraphite2.so.3",
        "libpng16.so.16",
        "libbrotlidec.so.1",
        "libbrotlicommon.so.1",
        "libbz2.so.1",
        "libz.so.1",
        "libglib-2.0.so.0",
        "libpcre2-8.so.0",
    }
)
"""Libraries left to the host. Everything else the executable links is bundled,
so a new dependency is carried by default rather than missing on a player's
machine."""

_LDD_LINE = re.compile(r"^\s*(?P<name>\S+)(?: => (?P<path>\S+|not found))?(?: \(0x[0-9a-f]+\))?$")

DESKTOP_ENTRY = f"""[Desktop Entry]
Type=Application
Name={PRODUCT_NAME}
Comment=The Legend of Zelda: The Wind Waker HD, presenting at 60 Hz
Exec={APP_NAME}
Icon={APP_NAME}
Categories=Game;
Terminal=false
"""

APP_RUN = f"""#!/bin/sh
# The package's entry point. It always names this product and the one title it
# runs, ahead of anything the player adds; the runtime refuses an added
# --title-id or --product-name naming another.
here="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$here/usr/lib${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
exec "$here/usr/bin/wiiuport" --product-name "{PRODUCT_NAME}" --title-id {TITLE_ID} "$@"
"""


class PackageRefused(RuntimeError):
    """The package could not be made as it must be; the message says why."""


@dataclass(frozen=True)
class Library:
    name: str
    path: Path


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(command), capture_output=True, text=True, check=False)


def parse_ldd(output: str) -> list[Library]:
    """Every library `ldd` resolved. A library it could not find, or a line it
    did not recognise, refuses: either would ship a package that fails to
    start on the player's machine."""
    libraries: list[Library] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        match = _LDD_LINE.match(line)
        if match is None:
            raise PackageRefused(f"ldd printed a line this cannot read: {line.strip()}")
        name, path = match.group("name"), match.group("path")
        if path == "not found":
            raise PackageRefused(f"{name} is not installed, so the executable cannot start")
        libraries.append(Library(Path(name).name, Path(path) if path else Path(name)))
    if not libraries:
        raise PackageRefused("ldd listed no libraries at all, which no dynamic executable has")
    return libraries


def libraries_to_bundle(libraries: Sequence[Library]) -> list[Library]:
    return [library for library in libraries if library.name not in HOST_PROVIDED]


def glibc_floor(binary_symbols: str) -> str:
    """The newest GLIBC symbol version the executable needs, from `objdump -T`."""
    versions = {
        tuple(int(part) for part in found.split("."))
        for found in re.findall(r"GLIBC_(\d+(?:\.\d+)+)", binary_symbols)
    }
    if not versions:
        raise PackageRefused("the executable names no glibc version, so its floor is unknown")
    return ".".join(str(part) for part in max(versions))


def refuse_build_paths(binary: Path, build_paths: Sequence[Path]) -> None:
    """Refuse an executable that names a private build path.

    A path compiled in -- ``__FILE__`` in an assert or a log line, a library's
    configured install directory -- would hand every player the builder's
    home. The runtime's build maps its own sources relative to its checkout;
    dependencies that record their install prefix must be built somewhere
    that names no one.
    """
    contents = binary.read_bytes()
    for path in build_paths:
        found = contents.count(str(path).encode())
        if found:
            raise PackageRefused(
                f"{binary} names {path} {found} times; build the runtime with its "
                "compiled paths made relative to the checkout"
            )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def icon_png(size: int = 256) -> bytes:
    """An original icon, drawn here: a white sail on a sea-blue disc."""
    rows = bytearray()
    centre = (size - 1) / 2
    for y in range(size):
        rows.append(0)
        for x in range(size):
            inside_disc = (x - centre) ** 2 + (y - centre) ** 2 <= (size * 0.47) ** 2
            top, bottom = size * 0.18, size * 0.72
            mast = size * 0.52
            reach = (y - top) / (bottom - top)
            in_sail = top <= y <= bottom and mast - reach * size * 0.3 <= x <= mast
            in_hull = size * 0.75 <= y <= size * 0.8 and size * 0.28 <= x <= size * 0.72
            if in_sail or in_hull:
                rows += bytes((250, 250, 245, 255))
            elif inside_disc:
                rows += bytes((31, 102, 160, 255))
            else:
                rows += bytes((0, 0, 0, 0))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _png_chunk(b"IEND", b"")
    )


def verified_type2_runtime(cache: Path, download: Callable[[str, Path], None]) -> Path:
    """The pinned AppImage runtime, fetched once and checked every time."""
    if not cache.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        download(TYPE2_RUNTIME_URL, cache)
    digest = hashlib.sha256(cache.read_bytes()).hexdigest()
    if digest != TYPE2_RUNTIME_SHA256:
        raise PackageRefused(
            f"{cache} has sha256 {digest}, not the pinned {TYPE2_RUNTIME_SHA256}; "
            "delete it to fetch the pinned runtime again"
        )
    return cache


def stage(
    appdir: Path,
    runtime: RuntimeCheckout,
    bundled: Sequence[Library],
    build_paths: Sequence[Path],
) -> None:
    """Lay the AppDir out. The executable keeps its data directories beside it,
    where the runtime resolves them."""
    binary_dir = appdir / "usr" / "bin"
    library_dir = appdir / "usr" / "lib"
    binary_dir.mkdir(parents=True)
    library_dir.mkdir(parents=True)
    stripped = subprocess.run(
        ["strip", "-o", str(binary_dir / "wiiuport"), str(runtime.product_binary)],
        capture_output=True,
        text=True,
        check=False,
    )
    if stripped.returncode != 0:
        raise PackageRefused(f"strip failed on the runtime executable:\n{stripped.stderr}")
    refuse_build_paths(binary_dir / "wiiuport", build_paths)
    for data in ("resources", "gameProfiles"):
        source = runtime.product_binary.parent / data
        if not source.is_dir():
            raise PackageRefused(f"the runtime's {data} directory is missing at {source}")
        shutil.copytree(source, binary_dir / data)
    for library in bundled:
        shutil.copy2(library.path, library_dir / library.name)
    app_run = appdir / "AppRun"
    app_run.write_text(APP_RUN)
    app_run.chmod(0o755)
    (appdir / f"{APP_NAME}.desktop").write_text(DESKTOP_ENTRY)
    icon = icon_png()
    (appdir / f"{APP_NAME}.png").write_bytes(icon)
    (appdir / ".DirIcon").write_bytes(icon)


def pack(appdir: Path, type2_runtime: Path, output: Path, run: Runner = _run) -> None:
    """Squash the AppDir and put the AppImage runtime in front of it."""
    image = output.with_suffix(".squashfs")
    squashed = run(
        [
            "mksquashfs",
            str(appdir),
            str(image),
            "-root-owned",
            "-noappend",
            "-comp",
            "zstd",
            "-quiet",
        ]
    )
    if squashed.returncode != 0:
        raise PackageRefused(f"mksquashfs failed:\n{squashed.stdout}{squashed.stderr}")
    output.write_bytes(type2_runtime.read_bytes() + image.read_bytes())
    output.chmod(0o755)
    image.unlink()


ANOTHER_TITLE_ID = "00050000101c9400"
"""Any title but this product's, for the package's own start-up check."""


def check_package(package: Path, run: Runner = _run) -> str:
    """Start the package told to run another title, which it must refuse.

    The refusal can only come from the runtime itself, so seeing it proves the
    image mounts, the launcher runs, the bundled and host libraries resolve,
    and the launcher named this title -- without a window or a disc.
    """
    result = run([str(package), "--title-id", ANOTHER_TITLE_ID])
    output = result.stdout + result.stderr
    expected = f"{PRODUCT_NAME} runs {TITLE_ID}, not {ANOTHER_TITLE_ID}"
    if result.returncode != 2 or expected not in output:
        raise PackageRefused(
            f"the package did not refuse another title as the runtime does "
            f"(exit {result.returncode}, wanted 2 and '{expected}'):\n{output.strip()}"
        )
    return expected
