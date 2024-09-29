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

    def _fence_pyimports_iter(self) -> Iterator[str]:
        for locator in self.conf.modules_by_path.values():
            yield locator.pyimport

        if isinstance(self.conf.fence, list):
            for value in self.conf.fence:
                if isinstance(value, str):
                    yield qik.conf.pyimport(value)
                else:
                    space = load(value.name)
                    yield from space._fence_pyimports_iter()

    def _fence_paths_iter(self) -> Iterator[str]:
        for locator in self.conf.modules_by_path.values():
            yield locator.path

        if isinstance(self.conf.fence, list):
            for value in self.conf.fence:
                if isinstance(value, str):
                    yield value
                elif value.name != self.name:
                    space = load(value.name)
                    yield from space._fence_paths_iter()

    @qik.func.cached_property
    def fence_pyimports(self) -> list[str]:
        try:
            return sorted(set(self._fence_pyimports_iter()))
        except RecursionError as e:
            raise qik.errors.CircularFence("Circular fence detected.") from e

    @qik.func.cached_property
    def fence_paths(self) -> list[str]:
        try:
            return sorted(set(self._fence_paths_iter()))
        except RecursionError as e:
            raise qik.errors.CircularFence("Circular fence detected.") from e

    @qik.func.cached_property
    def venv(self) -> qik.venv.Venv:
        if isinstance(self.conf.venv, str):
            conf = qik.conf.default_venv_type()(reqs=self.conf.venv)
        else:
            conf = self.conf.venv

        try:
            if conf is None or isinstance(conf, qik.conf.ActiveVenv):
                return qik.venv.active()
            elif isinstance(conf, qik.conf.SpaceVenv):
                if conf.name == self.name:
                    return qik.venv.active()
                else:
                    return load(conf.name).venv
            else:
                factory = qik.conf.get_type_factory(conf)
                return pkgutil.resolve_name(factory)(self.name, conf)
        except RecursionError as e:
            raise qik.errors.CircularVenv("Circular venv detected.") from e

    @property
    def environ(self) -> dict[str, str]:
        return self.venv.environ


@qik.func.cache
def load(name: str = "default") -> Space:
    """Get configuration for a space."""
    proj = qik.conf.project()
    if name != "default" and name not in proj.resolved_spaces:
        raise qik.errors.SpaceNotFound(f'Space "{name}" not configured.')

    return Space(name=name, conf=proj.resolved_spaces.get(name, qik.conf.Space()))
