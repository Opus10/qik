import msgspec

import qik.conf
import qik.errors
import qik.func
import qik.venv


class Space(msgspec.Struct, frozen=True, dict=True):
    name: str
    conf: qik.conf.Space

    @qik.func.cached_property
    def venv(self) -> qik.venv.Venv:
        if isinstance(self.conf.venv, str):
            return load(self.conf.venv).venv
        else:
            return qik.venv.factory(self.name, conf=self.conf.venv)


@qik.func.cache
def load(name: str = "default") -> Space:
    """Get configuration for a space."""
    proj = qik.conf.project()
    if name != "default" and name not in proj.spaces:
        raise qik.errors.SpaceNotFound(f'Space "{name}" not configured.')

    return Space(name=name, conf=proj.spaces.get(name, qik.conf.Space(venv="default")))
