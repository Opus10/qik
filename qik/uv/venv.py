from __future__ import annotations

import os
import pathlib
from typing import TYPE_CHECKING

import qik.cmd
import qik.conf
import qik.dep
import qik.errors
import qik.func
import qik.space
import qik.unset
import qik.uv.conf
import qik.uv.utils
import qik.venv

if TYPE_CHECKING:
    from qik.uv.qikplugin import UVVenvConf


def _resolve_constraint(
    constraint: str | qik.conf.SpaceLocator | qik.unset.UnsetType | None,
) -> str | qik.unset.UnsetType | None:
    if isinstance(constraint, str):
        return constraint
    elif isinstance(constraint, qik.conf.SpaceLocator):
        venv = qik.space.load(constraint.name).venv
        return (
            _resolve_constraint(venv.conf.constraint)
            if isinstance(venv, UVVenv)
            else qik.unset.UNSET
        )
    else:
        return constraint


class UVVenv(qik.venv.Venv, frozen=True, dict=True):
    conf: UVVenvConf

    @qik.func.cached_property
    def python(self) -> str | None:
        return qik.unset.coalesce(self.conf.python, qik.uv.conf.get().python, default=None)

    @qik.func.cached_property
    def constraint(self) -> str | None:
        try:
            return qik.unset.coalesce(
                _resolve_constraint(self.conf.constraint),
                _resolve_constraint(qik.uv.conf.get().constraint),
                default=None,
            )
        except RecursionError as e:
            raise qik.errors.CircularConstraint("Circular constraint detected.") from e

    @qik.func.cached_property
    def default_lock(self) -> str:
        uv_conf = qik.uv.conf.get()
        root = (
            qik.conf.pub_work_dir(rel=True)
            if uv_conf.resolved_cache == "repo"
            else qik.conf.priv_work_dir(rel=True)
        )
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
        raise AssertionError(
            f'Could not find site packages dir of venv "{self.name}" at "{self.dir}"'
        )

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
