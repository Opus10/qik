import subprocess
from typing import Literal, overload

import qik.conf
import qik.ctx


@overload
def exec(cmd: str, /, *, check: bool = ...) -> subprocess.CompletedProcess[str]: ...


@overload
def exec(cmd: str, /, *, lines: Literal[True], check: bool = ...) -> list[str]: ...


@overload
def exec(
    cmd: str, /, *, lines: Literal[False], check: bool = ...
) -> subprocess.CompletedProcess[str]: ...


def exec(
    cmd: str, /, *, lines: bool = False, check: bool = False, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str] | list[str]:
    """Run a shell commmand.

    If lines=True, return stdout as parsed lines.
    """
    result = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True,
        check=check,
        env=env,
        cwd=qik.conf.root(),
    )
    if not lines:
        return result
    else:
        stdout = result.stdout.strip()
        return stdout.split("\n") if stdout else []


def popen(cmd: str, env: dict[str, str] | None = None) -> subprocess.Popen:
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=True,
        bufsize=1,
        universal_newlines=True,
        env=env,
        cwd=qik.conf.root(),
    )
