from __future__ import annotations

import pkgutil
from typing import TYPE_CHECKING, Iterator

import msgspec

import qik.conf
import qik.errors
import qik.func
import qik.unset

if TYPE_CHECKING:
    from qik.runnable import Runnable


class Cmd(msgspec.Struct, frozen=True):
    name: str
    runnables: dict[str, Runnable]


@qik.func.cache
def load(name: str, **args: str) -> Cmd:
    """Load a command object."""
    cmd_conf = qik.conf.command(name)
    runnables = pkgutil.resolve_name(cmd_conf.factory or "qik.runnable.factory")(
        name, cmd_conf, **args
    )
    return Cmd(name=name, runnables=runnables)


def runnables(name: str) -> Iterator[Runnable]:
    """Load runnables for a command."""
    try:
        yield from load(name).runnables.values()
    except qik.errors.ArgNotSupplied:

        def _runnable_edges(runnable: Runnable) -> Iterator[Runnable]:
            if runnable.name.startswith(name):
                yield runnable

            for dep in runnable.deps_collection.runnables.values():
                yield from _runnable_edges(dep.obj)

        # Some commands, such as uv.install, take arguments and are included by
        # other commands. Allow the user to type the command name, which will
        # load the graph and return all runnables.
        for cmd in ls():
            for runnable in runnables(cmd):
                yield from _runnable_edges(runnable)


def ls() -> Iterator[str]:
    """List all non-hidden command names."""
    proj = qik.conf.project()
    for module in [None, *proj.modules_by_name, *proj.plugins_by_name]:
        conf = qik.conf.search(module)
        for command in conf.commands:
            cmd_name = f"{module}/{command}" if module else command
            if not qik.conf.command(cmd_name).hidden:
                yield cmd_name
