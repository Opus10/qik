from __future__ import annotations

import platform
from typing import TYPE_CHECKING, Literal, TypeAlias

if TYPE_CHECKING:
    ArchType: TypeAlias = Literal[
        "win-64",
        "win-32",
        "linux-64",
        "linux-aarch64",
        "linux-ppc64le",
        "linux-32",
        "osx-arm64",
        "osx-64",
    ]


def get() -> ArchType:
    """Get the architecture of a machine."""
    system = platform.system()
    arch = platform.architecture()[0]
    machine = platform.machine()

    if system == "Windows":
        return "win-64" if arch == "64bit" else "win-32"
    elif system == "Linux":
        if machine == "x86_64":
            return "linux-64"
        elif machine == "aarch64":
            return "linux-aarch64"
        elif machine == "ppc64le":
            return "linux-ppc64le"
        elif arch == "32bit":
            return "linux-32"
    elif system == "Darwin":
        if arch == "64bit":
            return "osx-arm64" if machine == "arm64" else "osx-64"

    return "unknown"
