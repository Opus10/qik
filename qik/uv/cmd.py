from __future__ import annotations

import functools

import qik.conf
import qik.dep
import qik.errors
import qik.runnable


def lock_cmd(runnable: qik.runnable.Runnable) -> tuple[int, str]:
    """Lock the virtual env."""
    return 0, "Locked!"


@functools.cache
def lock_cmd_name() -> str:
    plugin_name = qik.conf.plugin_locator("qik.uv", by_pyimport=True).name
    return f"{plugin_name}.lock"


def lock_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    venv = args.get("venv")
    if not venv:
        raise qik.errors.ArgNotSupplied('"venv" arg is required for qik.uv.lock command.')

    cmd_name = lock_cmd_name()
    print("cmd_name", cmd_name)

    runnable = qik.runnable.Runnable(
        name=f"{cmd_name}?venv={venv}",
        cmd=cmd_name,
        val="qik.uv.cmd.lock_cmd",
        shell=False,
        deps=[],
        artifacts=[],
        cache="repo",
        args={"venv": venv},
    )
    return {runnable.name: runnable}


@functools.cache
def install_cmd_name() -> str:
    plugin_name = qik.conf.plugin_locator("qik.uv", by_pyimport=True).name
    return f"{plugin_name}.install"


def install_cmd(runnable: qik.runnable.Runnable) -> tuple[int, str]:
    """Install the virtual env."""
    return 0, "Installed!"


def install_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    venv = args.get("venv")
    if not venv:
        raise qik.errors.ArgNotSupplied('"venv" arg is required for qik.uv.install command.')

    cmd_name = install_cmd_name()
    runnable = qik.runnable.Runnable(
        name=f"{cmd_name}?venv={venv}",
        cmd=cmd_name,
        val="qik.uv.cmd.install_cmd",
        shell=False,
        deps=[qik.dep.Cmd(lock_cmd_name(), args={"venv": venv})],
        artifacts=[],
        cache="repo",
        args={"venv": venv},
        space=None,
    )
    return {runnable.name: runnable}
