import subprocess
from typing import Literal, overload


@overload
def exec(cmd: str, /, *, check: bool = ...) -> subprocess.CompletedProcess[str]: ...


@overload
def exec(cmd: str, /, *, lines: Literal[True], check: bool = ...) -> list[str]: ...


@overload
def exec(
    cmd: str, /, *, lines: Literal[False], check: bool = ...
) -> subprocess.CompletedProcess[str]: ...


def exec(
    cmd: str, /, *, lines: bool = False, check: bool = False
) -> subprocess.CompletedProcess[str] | list[str]:
    """Run a shell commmand.

    If lines=True, return stdout as parsed lines.
    """
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, check=check)
    if not lines:
        return result
    else:
        stdout = result.stdout.strip()
        return stdout.split("\n") if stdout else []
