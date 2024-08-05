from __future__ import annotations

import builtins
import pathlib
import shutil
from typing import IO, TYPE_CHECKING, Literal, TypeAlias

import qik.conf

if TYPE_CHECKING:
    PathLike: TypeAlias = pathlib.Path | str

_builtin_open = builtins.open


def make_parent_dirs(path: pathlib.Path) -> None:
    """Create parent dirs of a path.

    Ensures we properly create the structure of our local
    qik cache.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if str(path.resolve()).startswith(str(qik.conf.priv_work_dir())):
        # Ensure our project cache directory always has a .gitignore
        (qik.conf.priv_work_dir() / ".gitignore").write_text("*")


def open(path: PathLike, mode: Literal["w"] = "w") -> IO[str]:
    try:
        return _builtin_open(path, "w")
    except FileNotFoundError:
        make_parent_dirs(path)
        return _builtin_open(path, "w")


def copy(src: PathLike, dest: PathLike) -> None:
    """Copy a file, trying again if the parent dirs don't exist."""
    src_path = pathlib.Path(src)
    dest_path = pathlib.Path(dest)
    try:
        shutil.copy(src_path, dest_path)
    except FileNotFoundError:
        make_parent_dirs(dest_path)
        shutil.copy(src_path, dest_path)


def write(location: PathLike, val: bytes | str) -> None:
    """Write bytes to a file."""
    location_path = pathlib.Path(location)
    writer = location_path.write_text if isinstance(val, str) else location_path.write_bytes
    try:
        writer(val)
    except FileNotFoundError:
        make_parent_dirs(location_path)
        writer(val)
