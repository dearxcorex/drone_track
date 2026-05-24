"""Hatchling custom build hook: build libopendroneid via CMake and copy into _lib/."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class LibopendroneidBuildHook(BuildHookInterface):
    PLUGIN_NAME = "build_libopendroneid"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        vendor = root / "vendor" / "opendroneid-core-c"
        if not vendor.exists():
            raise RuntimeError(
                "vendor/opendroneid-core-c not found; run "
                "`git submodule update --init --recursive`"
            )
        build_dir = vendor / "build"
        build_dir.mkdir(exist_ok=True)
        subprocess.run(
            [
                "cmake",
                "-S", str(vendor),
                "-B", str(build_dir),
                "-DBUILD_MAVLINK=OFF",
                "-DBUILD_WIFI=OFF",
                "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
            ],
            check=True,
        )
        subprocess.run(
            [
                "cmake", "--build", str(build_dir),
                "--config", "Release",
                "--target", "opendroneid",
            ],
            check=True,
        )
        dest = root / "src" / "drone_detector" / "_lib"
        dest.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            built = next(build_dir.rglob("libopendroneid.dylib"))
        else:
            built = next(build_dir.rglob("libopendroneid.so*"))
        shutil.copy2(built, dest / built.name)
        build_data["force_include"][str(dest / built.name)] = (
            f"drone_detector/_lib/{built.name}"
        )
