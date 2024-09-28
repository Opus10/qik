import pkgutil
from typing import Iterator

import msgspec

import qik.conf
import qik.errors
import qik.func
import qik.venv


class Space(msgspec.Struct, frozen=True, dict=True):
    name: str
    conf: qik.conf.Space

    def _pyimports_iter(self) -> Iterator[str]:
        for locator in self.conf.modules_by_path.values():
            yield locator.pyimport

        for value in self.conf.fence:
            if isinstance(value, str):
                yield qik.conf.pyimport(value)
            else:
                space = load(value.name)
                yield from space._pyimports_iter()

    @qik.func.cached_property
    def fence_pyimports(self) -> list[str]:
        try:
            return sorted(set(self._pyimports_iter()))
        except RecursionError as e:
            raise qik.errors.CircularFence("Circular fence detected.") from e

    @qik.func.cached_property
    def venv(self) -> qik.venv.Venv:
        try:
            if self.conf.venv is None or isinstance(self.conf.venv, qik.conf.ActiveVenv):
                return qik.venv.active()
            elif isinstance(self.conf.venv, qik.conf.SpaceVenv):
                return load(self.conf.venv.name).venv
            else:
                factory = qik.conf.get_type_factory(self.conf.venv)
                return pkgutil.resolve_name(factory)(self.name, self.conf.venv)
        except RecursionError as e:
            raise qik.errors.CircularVenv("Circular venv detected.") from e


@qik.func.cache
def load(name: str = "default") -> Space:
    """Get configuration for a space."""
    proj = qik.conf.project()
    if name != "default" and name not in proj.spaces:
        raise qik.errors.SpaceNotFound(f'Space "{name}" not configured.')

    return Space(name=name, conf=proj.spaces.get(name, qik.conf.Space()))
