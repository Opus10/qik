"""Core hashing functions."""

from __future__ import annotations

import collections
import importlib.metadata
import subprocess
from typing import TYPE_CHECKING

import xxhash

import qik.shell

if TYPE_CHECKING:
    import qik.dep as run_deps


def globs(*vals: run_deps.Glob | str) -> str:
    """Compute a hash string of glob patterns.

    Use git ls-files, tracking both added and modified file hashes.
    """
    if not vals:
        return ""

    fmt = "--format '%(path)\t%(objectname)'"
    # Create a pattern string for git ls-files. Ensure there are no duplicates and
    # that we sort globs for a consistent hash
    pattern_str = " ".join(sorted({f"'{glob}'" for glob in vals}))
    git_ls_lines = qik.shell.exec(f"git ls-files -cm {fmt} {pattern_str}", check=True, lines=True)
    git_ls_lines_split = [line.split("\t", 1) for line in git_ls_lines]
    hashes = dict(git_ls_lines_split)

    # Files that are modified appear twice. Manually compute their hashes
    path_counts = collections.Counter(line[0] for line in git_ls_lines_split)
    modified = [path for path, count in path_counts.items() if count > 1]
    if modified:
        try:
            modified_hashes_lines = qik.shell.exec(
                f"git ls-files --format '%(path)' {pattern_str} -m | xargs git hash-object",
                check=True,
                lines=True,
            )
        except subprocess.CalledProcessError:
            # If there are issues with the first command, it likely means a file does
            # not exist. Do the suboptimal strategy here, piping individual files to
            # `git hash-object` while printing zeroes for files that no longer exist.
            cmd = f"""
                git ls-files --format '%(path)' {pattern_str} -m | while IFS= read -r file; do
                    if [ -f "$file" ]; then
                        git hash-object "$file"
                    else
                        echo "0000000000000000000000000000000000000000"
                    fi
                done
            """
            modified_hashes_lines = qik.shell.exec(cmd, check=True, lines=True)

        for i, name in enumerate(modified):
            hashes[name] = modified_hashes_lines[i]

    return xxhash.xxh128_hexdigest("".join(f"{name}{hash}" for name, hash in hashes.items()))


def dists(*vals: str) -> str:
    return xxhash.xxh128_hexdigest(
        "".join(f"{dist}{importlib.metadata.version(dist)}" for dist in sorted(vals))
    )


def strs(*vals: str) -> str:
    return xxhash.xxh128_hexdigest("".join(sorted(vals)))


def val(input: str | bytes) -> str:
    return xxhash.xxh128_hexdigest(input)
