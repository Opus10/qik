import functools

import msgspec

import qik.conf
import qik.errors


class Space(msgspec.Struct, frozen=True, dict=True):
    conf: qik.conf.Space


@functools.cache
def load(name: str = "default") -> Space:
    """Get configuration for a space."""
    proj = qik.conf.project()
    if name != "default" and name not in proj.spaces:
        raise qik.errors.SpaceNotFound(f'Space "{name}" not configured.')

    return Space(conf=proj.spaces.get(name, qik.conf.Space(venv="default")))
