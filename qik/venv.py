from __future__ import annotations

import functools
import os
import pathlib
import sysconfig

import msgspec

import qik.cmd
import qik.conf
import qik.dep
import qik.errors
import qik.uv.cmd


class Venv(msgspec.Struct, frozen=True, dict=True):
    name: str
    conf: qik.conf.Venv

    @functools.cached_property
    def reqs(self) -> list[str]:
        return self.conf.reqs if isinstance(self.conf.reqs, list) else [self.conf.reqs]

    @property
    def environ(self) -> dict[str, str]:
        return os.environ  # type: ignore

    @property
    def dir(self) -> pathlib.Path:
        raise NotImplementedError

    @functools.cached_property
    def rel_dir(self) -> pathlib.Path:
        return pathlib.Path(self.dir).relative_to(qik.conf.root())

    @property
    def lock(self) -> str | None:
        return self.conf.lock

    @functools.cached_property
    def rel_lock(self) -> str | None:
        return str(pathlib.Path(self.lock).relative_to(qik.conf.root())) if self.lock else None

    @functools.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        raise NotImplementedError

    @functools.cached_property
    def glob_deps(self) -> set[str]:
        return {self.lock} if self.lock else set()


class Active(Venv, frozen=True, dict=True):
    """
    The active virtual environment.
    """

    conf: qik.conf.ActiveVenv

    @property
    def dir(self) -> pathlib.Path:
        return pathlib.Path(sysconfig.get_path("purelib"))

    @property
    def rel_dir(self) -> pathlib.Path:  # type: ignore
        return self.dir

    @functools.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        return {}


class UV(Venv, frozen=True, dict=True):
    """
    TODO: Move this Venv definition into qik.uv.venv module
    once we have a plugin system in place.
    """

    conf: qik.conf.UVVenv

    @functools.cached_property
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

    @property
    def rel_lock(self) -> str:  # type: ignore
        return super().rel_lock  # type: ignore

    @functools.cached_property
    def environ(self) -> dict[str, str]:  # type: ignore
        return os.environ | {
            "VIRTUAL_ENV": str(self.dir),
            "PATH": f"{self.dir}/bin:{os.environ['PATH']}",
        }

    @functools.cached_property
    def dir(self) -> pathlib.Path:  # type: ignore
        return qik.conf.priv_work_dir() / "venv" / self.name

    @functools.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        return {
            runnable.name: qik.dep.Runnable(name=runnable.name, obj=runnable, strict=False)
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
