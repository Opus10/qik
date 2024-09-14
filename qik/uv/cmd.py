from __future__ import annotations

import functools
import pathlib
from typing import cast

import qik.conf
import qik.dep
import qik.errors
import qik.runnable
import qik.space
import qik.venv


@functools.cache
def lock_cmd_name() -> str:
    plugin_name = qik.conf.plugin_locator("qik.uv", by_pyimport=True).name
    return f"{plugin_name}.lock"


def lock_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    venv_name = args.get("venv")
    if not venv_name:
        raise qik.errors.ArgNotSupplied('"venv" arg is required for qik.uv.lock command.')

    venv = cast(qik.venv.UV, qik.space.load(venv_name).venv)
    cmd_name = lock_cmd_name()
    runnable = qik.runnable.Runnable(
        name=f"{cmd_name}?venv={venv_name}",
        cmd=cmd_name,
        val=f"mkdir -p {pathlib.Path(venv.rel_lock).parent} && uv pip compile --universal {' '.join(venv.reqs)} -o {venv.rel_lock}",
        deps=[qik.dep.Pydist("uv"), *(qik.dep.Glob(req) for req in venv.reqs)],
        artifacts=[venv.lock],
        cache="repo",
        args={"venv": venv_name},
    )
    return {runnable.name: runnable}


@functools.cache
def install_cmd_name() -> str:
    plugin_name = qik.conf.plugin_locator("qik.uv", by_pyimport=True).name
    return f"{plugin_name}.install"


def install_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    venv_name = args.get("venv")
    if not venv_name:
        raise qik.errors.ArgNotSupplied('"venv" arg is required for qik.uv.install command.')

    venv = cast(qik.venv.UV, qik.space.load(venv_name).venv)
    cmd_name = install_cmd_name()
    runnable = qik.runnable.Runnable(
        name=f"{cmd_name}?venv={venv_name}",
        cmd=cmd_name,
        val=f"uv venv {venv.rel_dir} && uv pip sync {venv.rel_lock} --python {venv.rel_dir}/bin/python",
        deps=[
            qik.dep.Cmd(lock_cmd_name(), args={"venv": venv_name}),
            qik.dep.Glob(venv.lock),
        ],
        artifacts=[],
        cache="local",
        args={"venv": venv_name},
        space=None,
    )
    return {runnable.name: runnable}
