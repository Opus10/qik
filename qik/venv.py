import functools
import pathlib
import sysconfig

import msgspec

import qik.conf


class Env(msgspec.Struct, frozen=True, dict=True):
    name: str
    lock_file: list[str] = []

    @functools.cached_property
    def dir(self) -> pathlib.Path:
        return pathlib.Path(sysconfig.get_path("purelib"))


@functools.cache
def load(name: str = "default") -> Env:
    """Load an env."""
    proj = qik.conf.project()
    if conf := proj.venvs.get(name):
        lock_file = conf.lock_file if isinstance(conf.lock_file, list) else [conf.lock_file]
        return Env(name=name, lock_file=lock_file)
    elif name == "default":
        return Env(name="default")
    else:
        raise KeyError(f'Venv named "{name}" not configured in qik.venvs.')
