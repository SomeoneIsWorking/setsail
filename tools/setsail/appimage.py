"""The player's package: an asset-free AppImage of the runtime, made for this title.

The AppImage holds the runtime's release bundle -- its executable, the data it
reads beside it, and the libraries a desktop cannot be assumed to have -- and a
launcher that always names this product and title. It holds no game files, keys or anything derived from them:
the player chooses their own disc image on the runtime's first-run screen.

The bundle is built by the runtime in its release container, which sets the
glibc the package needs; that floor is reported, never hidden.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import zlib
from collections.abc import Callable, Sequence
from pathlib import Path

from setsail.gamefile import TITLE_ID

APP_NAME = "setsail"
PRODUCT_NAME = "Set Sail"
"""What the player sees the product called, on its window and first-run screen."""

TYPE2_RUNTIME_URL = (
    "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64"
)
TYPE2_RUNTIME_SHA256 = "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"
"""The AppImage runtime prepended to the image, pinned by release and checksum."""

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


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(command), capture_output=True, text=True, check=False)


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


BUNDLE_MANIFEST = "runtime.json"
BUNDLE_LAYOUT = {"executable": "usr/bin/wiiuport", "libraries": "usr/lib"}
"""Where the runtime's bundle puts what the launcher above names."""


def stage(appdir: Path, bundle: Path) -> dict[str, object]:
    """Lay the AppDir out from the runtime's release bundle, and return its manifest.

    The bundle is the runtime's: its executable, data and libraries. This adds
    what makes it this product -- the launcher, the desktop entry and the icon.
    """
    manifest_path = bundle / BUNDLE_MANIFEST
    if not manifest_path.is_file():
        raise PackageRefused(f"{bundle} is not a staged runtime bundle: {manifest_path} is missing")
    manifest: dict[str, object] = json.loads(manifest_path.read_text())
    for key, expected in BUNDLE_LAYOUT.items():
        if manifest.get(key) != expected:
            raise PackageRefused(
                f"the bundle puts its {key} at {manifest.get(key)!r}, but the launcher runs "
                f"{expected!r}"
            )
    shutil.copytree(bundle / "usr", appdir / "usr")
    app_run = appdir / "AppRun"
    app_run.write_text(APP_RUN)
    app_run.chmod(0o755)
    (appdir / f"{APP_NAME}.desktop").write_text(DESKTOP_ENTRY)
    icon = icon_png()
    (appdir / f"{APP_NAME}.png").write_bytes(icon)
    (appdir / ".DirIcon").write_bytes(icon)
    return manifest


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
