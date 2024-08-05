from __future__ import annotations

import functools
import pkgutil
from typing import TYPE_CHECKING, Iterator

import msgspec

import qik.conf
import qik.unset

if TYPE_CHECKING:
    from qik.runnable import Runnable


class Cmd(msgspec.Struct, frozen=True):
    name: str
    runnables: dict[str, Runnable]


@functools.cache
def load(cmd: str) -> Cmd:
    """Load runnables for a command."""
    cmd_conf = qik.conf.command(cmd)
    runnables = pkgutil.resolve_name(cmd_conf.factory or "qik.runnable.factory")(cmd, cmd_conf)
    return Cmd(name=cmd, runnables=runnables)


def ls() -> Iterator[Cmd]:
    """List all commands."""
    proj = qik.conf.project()
    for module in [None, *proj.modules_by_name, *proj.plugins_by_name]:
        conf = qik.conf.get(module)
        for command in conf.commands:
            yield load(f"{module}.{command}") if module else load(command)
