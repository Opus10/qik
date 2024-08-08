import os
import subprocess
from typing import Literal, overload

import qik.conf
import qik.ctx


def _get_exec_env() -> dict[str, str]:
    return {
        **os.environ,
        "QIK__CMD": qik.ctx.runnable().cmd,
        "QIK__RUNNABLE": qik.ctx.runnable().name,
        "QIK__WORKER": str(qik.ctx.worker_id()),
    }


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
    result = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True,
        check=check,
        env=_get_exec_env(),
        cwd=qik.conf.root(),
    )
    if not lines:
        return result
    else:
        stdout = result.stdout.strip()
        return stdout.split("\n") if stdout else []


def popen(cmd: str) -> subprocess.Popen:
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=True,
        bufsize=1,
        universal_newlines=True,
        env=_get_exec_env(),
        cwd=qik.conf.root(),
    )
