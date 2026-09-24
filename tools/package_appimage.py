#!/usr/bin/env python3
"""Build the player's AppImage: build/appimage/setsail-x86_64.AppImage.

Brings the sibling runtime up to date through the launcher's own owner, lays
the package out, and refuses to hand over a package that does not start.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from setsail.appimage import (
    APP_NAME,
    PackageRefused,
    check_package,
    glibc_floor,
    libraries_to_bundle,
    pack,
    parse_ldd,
    stage,
    verified_type2_runtime,
)
from setsail.launch import LaunchRefused, bring_up_to_date, resolve_runtime

OUTPUT_DIR = ROOT / "build" / "appimage"


def _download(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        destination.write_bytes(response.read())


def _output_of(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise PackageRefused(f"{command[0]} failed:\n{result.stderr}")
    return result.stdout


def main() -> int:
    try:
        runtime = resolve_runtime(ROOT)
        bring_up_to_date(runtime)
        libraries = parse_ldd(_output_of(["ldd", str(runtime.product_binary)]))
        bundled = libraries_to_bundle(libraries)
        floor = glibc_floor(_output_of(["objdump", "-T", str(runtime.product_binary)]))
        appdir = OUTPUT_DIR / "AppDir"
        if appdir.exists():
            shutil.rmtree(appdir)
        # The builder's home names the person who built it.
        stage(appdir, runtime, bundled, (Path.home(),))
        type2 = verified_type2_runtime(OUTPUT_DIR / "runtime-x86_64", _download)
        package = OUTPUT_DIR / f"{APP_NAME}-x86_64.AppImage"
        pack(appdir, type2, package)
        refusal = check_package(package)
    except (LaunchRefused, PackageRefused) as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    size = package.stat().st_size / (1024 * 1024)
    print(f"packaged {package} ({size:.1f} MiB)")
    print(
        f"bundled {len(bundled)} of {len(libraries)} libraries: "
        + ", ".join(library.name for library in bundled)
    )
    print(f"needs glibc {floor} or newer on the player's machine")
    print(f"started and refused another title: '{refusal}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
