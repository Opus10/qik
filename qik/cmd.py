from __future__ import annotations

import pkgutil
from typing import TYPE_CHECKING, Iterator

import msgspec

import qik.conf
import qik.func
import qik.unset

if TYPE_CHECKING:
    from qik.runnable import Runnable


class Cmd(msgspec.Struct, frozen=True):
    name: str
    runnables: dict[str, Runnable]


@qik.func.cache
def load(name: str, **args: str) -> Cmd:
    """Load runnables for a command."""
    cmd_conf = qik.conf.command(name)
    runnables = pkgutil.resolve_name(cmd_conf.factory or "qik.runnable.factory")(
        name, cmd_conf, **args
    )
    return Cmd(name=name, runnables=runnables)


def ls() -> Iterator[str]:
    """List all non-hidden command names."""
    proj = qik.conf.project()
    for module in [None, *proj.modules_by_name, *proj.plugins_by_name]:
        conf = qik.conf.get(module)
        for command in conf.commands:
            cmd_name = f"{module}.{command}" if module else command
            if not qik.conf.command(cmd_name).hidden:
                yield cmd_name
