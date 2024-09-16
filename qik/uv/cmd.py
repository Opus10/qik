from __future__ import annotations

import pathlib
from typing import cast

import qik.conf
import qik.dep
import qik.errors
import qik.func
import qik.runnable
import qik.space
import qik.venv


@qik.func.cache
def lock_cmd_name() -> str:
    plugin_name = qik.conf.plugin_locator("qik.uv", by_pyimport=True).name
    return f"{plugin_name}.lock"


def lock_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    space = args.get("space")
    if not space:
        raise qik.errors.ArgNotSupplied('"space" arg is required for qik.uv.lock command.')

    venv = cast(qik.venv.UV, qik.space.load(space).venv)
    cmd_name = lock_cmd_name()
    runnable = qik.runnable.Runnable(
        name=f"{cmd_name}?space={space}",
        cmd=cmd_name,
        val=f"mkdir -p {pathlib.Path(venv.lock[0]).parent} && uv pip compile --universal {' '.join(venv.reqs)} -o {venv.lock[0]}",
        deps=[*(qik.dep.Glob(req) for req in venv.reqs), *qik.dep.project_deps()],
        artifacts=venv.lock,
        cache="repo",
        args={"space": space},
        space=None,
    )
    return {runnable.name: runnable}


@qik.func.cache
def install_cmd_name() -> str:
    plugin_name = qik.conf.plugin_locator("qik.uv", by_pyimport=True).name
    return f"{plugin_name}.install"


def install_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    space = args.get("space")
    if not space:
        raise qik.errors.ArgNotSupplied('"space" arg is required for qik.uv.install command.')

    venv = cast(qik.venv.UV, qik.space.load(space).venv)
    venv_python = f"--python '{venv.conf.python}'" if venv.conf.python else ""
    cmd_name = install_cmd_name()
    runnable = qik.runnable.Runnable(
        name=f"{cmd_name}?space={space}",
        cmd=cmd_name,
        val=f"uv venv {venv.dir} {venv_python} && uv pip sync {venv.lock[0]} --python {venv.dir}/bin/python",
        deps=[
            qik.dep.Cmd(lock_cmd_name(), args={"space": space}, strict=True),
            qik.dep.Glob(venv.lock[0]),
            *qik.dep.project_deps(),
        ],
        artifacts=[],
        cache="local",
        args={"space": space},
        space=None,
    )
    return {runnable.name: runnable}
