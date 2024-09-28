from __future__ import annotations

import os
import pathlib
from typing import TYPE_CHECKING

import qik.cmd
import qik.conf
import qik.dep
import qik.errors
import qik.func
import qik.uv.conf
import qik.uv.utils
import qik.venv

if TYPE_CHECKING:
    from qik.uv.qikplugin import UVVenvConf


class UVVenv(qik.venv.Venv, frozen=True, dict=True):
    conf: UVVenvConf

    @qik.func.cached_property
    def python(self) -> str | None:
        return self.conf.python or qik.uv.conf.get().python

    @qik.func.cached_property
    def default_lock(self) -> str:
        uv_conf = qik.uv.conf.get()
        root = qik.conf.pub_work_dir() if uv_conf.cache == "repo" else qik.conf.priv_work_dir()
        return str(
            root
            / "artifacts"
            / qik.uv.utils.lock_cmd_name()
            / f"requirements-{self.name}-lock.txt"
        )

    @qik.func.cached_property
    def lock(self) -> str:
        super_lock = super().lock
        return self.default_lock if not super_lock else super_lock

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
    def site_packages_dir(self) -> pathlib.Path:  # type: ignore
        for path in pathlib.Path(self.dir).glob("lib/python*/site-packages"):
            return path

        # TODO: Turn this into a qik runtime error
        raise AssertionError(f'Could not find site packages dir of venv "{self.name}"')

    @qik.func.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        return {
            runnable.name: qik.dep.Runnable(name=runnable.name, obj=runnable, strict=True)
            for runnable in qik.cmd.load(
                qik.uv.utils.install_cmd_name(), space=self.name
            ).runnables.values()
        }


def factory(name: str, conf: UVVenvConf) -> UVVenv:
    return UVVenv(name=name, conf=conf)
