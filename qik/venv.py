from __future__ import annotations

import os
import pathlib
import sysconfig

import msgspec

import qik.cmd
import qik.conf
import qik.dep
import qik.errors
import qik.func
import qik.hash
import qik.uv.cmd


class Venv(msgspec.Struct, frozen=True, dict=True):
    name: str
    conf: qik.conf.Venv

    @qik.func.cached_property
    def reqs(self) -> list[str]:
        return self.conf.reqs if isinstance(self.conf.reqs, list) else [self.conf.reqs]

    @property
    def environ(self) -> dict[str, str]:
        return os.environ  # type: ignore

    @property
    def dir(self) -> pathlib.Path:
        raise NotImplementedError

    @property
    def lock(self) -> str | None:
        return self.conf.lock

    @qik.func.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        raise NotImplementedError

    @qik.func.cached_property
    def glob_deps(self) -> set[str]:
        return {self.lock} if self.lock else set()

    @qik.func.cached_property
    def const_deps(self) -> set[str]:
        """Return the serialized venv as a constant dep."""
        return {msgspec.json.encode(self).decode()}


class Active(Venv, frozen=True, dict=True):
    """
    The active virtual environment.
    """

    conf: qik.conf.ActiveVenv

    @property
    def dir(self) -> pathlib.Path:
        return pathlib.Path(sysconfig.get_path("purelib"))

    @qik.func.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        return {}


class UV(Venv, frozen=True, dict=True):
    """
    TODO: Move this Venv definition into qik.uv.venv module
    once we have a plugin system in place.
    """

    conf: qik.conf.UVVenv

    @qik.func.cached_property
    def default_lock(self) -> str:
        return str(
            qik.conf.pub_work_dir()
            / "artifacts"
            / qik.uv.cmd.lock_cmd_name()
            / f"requirements-{self.name}-lock.txt"
        )

    @property
    def lock(self) -> str:
        return super().lock or self.default_lock

    @qik.func.cached_property
    def environ(self) -> dict[str, str]:  # type: ignore
        return os.environ | {
            "VIRTUAL_ENV": str(self.dir),
            "PATH": f"{self.dir}/bin:{os.environ['PATH']}",
        }

    @qik.func.cached_property
    def dir(self) -> pathlib.Path:  # type: ignore
        return qik.conf.priv_work_dir() / "venv" / self.name

    @qik.func.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        return {
            runnable.name: qik.dep.Runnable(name=runnable.name, obj=runnable, strict=True)
            for runnable in qik.cmd.load(
                qik.uv.cmd.install_cmd_name(), venv=self.name
            ).runnables.values()
        }


def factory(name: str = "default", *, conf: qik.conf.Venv | None = None) -> Venv:
    if isinstance(conf, qik.conf.ActiveVenv):
        return Active(name=name, conf=conf)
    elif isinstance(conf, qik.conf.UVVenv):
        return UV(name=name, conf=conf)
    elif conf is None:
        return Active(name=name, conf=qik.conf.ActiveVenv())
    else:
        raise qik.errors.VenvNotFound(f'Venv named "{name}" not configured in qik.venvs.')
