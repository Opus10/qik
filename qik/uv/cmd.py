from __future__ import annotations

import pathlib
from typing import cast

import qik.conf
import qik.dep
import qik.errors
import qik.func
import qik.runnable
import qik.space
import qik.uv.conf
import qik.uv.utils
import qik.uv.venv
import qik.venv


def lock_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    space = args.get("space")
    if not space:
        raise qik.errors.ArgNotSupplied('"space" arg is required for qik.uv.lock command.')

    venv = cast(qik.uv.venv.UVVenv, qik.space.load(space).venv)
    cmd_name = qik.uv.utils.lock_cmd_name()
    uv_conf = qik.uv.conf.get()
    runnable = qik.runnable.Runnable(
        name=f"{cmd_name}?space={space}",
        cmd=cmd_name,
        val=f"mkdir -p {pathlib.Path(venv.lock).parent} && uv pip compile --universal {' '.join(venv.reqs)} -o {venv.lock}",
        deps=[*qik.dep.base(), *(qik.dep.Glob(req) for req in venv.reqs)],
        artifacts=[venv.lock],
        cache=uv_conf.resolved_cache,
        cache_when="success",
        args={"space": space},
        space=None,
    )
    return {runnable.name: runnable}


def install_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    space = args.get("space")
    if not space:
        raise qik.errors.ArgNotSupplied('"space" arg is required for qik.uv.install command.')

    venv = cast(qik.uv.venv.UVVenv, qik.space.load(space).venv)
    venv_python = f"--python '{venv.conf.python}'" if venv.conf.python else ""
    cmd_name = qik.uv.utils.install_cmd_name()
    runnable = qik.runnable.Runnable(
        name=f"{cmd_name}?space={space}",
        cmd=cmd_name,
        val=f"uv venv {venv.dir} {venv_python} && uv pip sync {venv.lock} --python {venv.dir}/bin/python",
        deps=[
            *qik.dep.base(),
            qik.dep.Cmd(qik.uv.utils.lock_cmd_name(), args={"space": space}, strict=True),
            qik.dep.Glob(venv.lock),
        ],
        artifacts=[],
        cache="local",
        cache_when="success",
        args={"space": space},
        space=None,
    )
    return {runnable.name: runnable}
