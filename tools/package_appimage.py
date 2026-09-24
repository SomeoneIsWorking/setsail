#!/usr/bin/env python3
"""Build the player's AppImage: build/appimage/setsail-x86_64.AppImage.

Has the sibling runtime build its release bundle in its container, lays the
package out around it, and refuses to hand over a package that does not start.
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
    pack,
    stage,
    verified_type2_runtime,
)
from setsail.launch import LaunchRefused, resolve_runtime
from setsail.runtime import RuntimeCheckout

OUTPUT_DIR = ROOT / "build" / "appimage"


def _download(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        destination.write_bytes(response.read())


def build_release_runtime(runtime: RuntimeCheckout) -> None:
    """The runtime's own release build, in its container; its output is shown."""
    built = subprocess.run(
        ["uv", "run", "--frozen", "python", str(runtime.release_tool)],
        cwd=runtime.root,
        check=False,
    )
    if built.returncode != 0:
        raise PackageRefused(
            "the runtime's release build failed; its output is above. "
            "Not packaging the bundle that was there before."
        )


def main() -> int:
    try:
        runtime = resolve_runtime(ROOT)
        build_release_runtime(runtime)
        appdir = OUTPUT_DIR / "AppDir"
        if appdir.exists():
            shutil.rmtree(appdir)
        manifest = stage(appdir, runtime.release_bundle)
        type2 = verified_type2_runtime(OUTPUT_DIR / "runtime-x86_64", _download)
        package = OUTPUT_DIR / f"{APP_NAME}-x86_64.AppImage"
        pack(appdir, type2, package)
        refusal = check_package(package)
    except (LaunchRefused, PackageRefused) as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    size = package.stat().st_size / (1024 * 1024)
    print(f"packaged {package} ({size:.1f} MiB)")
    bundled = manifest["bundled"]
    print(f"bundled {len(bundled)} of {manifest['linked']} libraries: " + ", ".join(bundled))
    print(f"needs glibc {manifest['glibc_floor']} or newer on the player's machine")
    print(f"started and refused another title: '{refusal}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
