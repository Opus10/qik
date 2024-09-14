import functools
import os
import pathlib
import sysconfig

import msgspec

import qik.conf
import qik.errors
import qik.uv.cmd


class Venv(msgspec.Struct, frozen=True, dict=True):
    name: str
    conf: qik.conf.Venv

    @functools.cached_property
    def reqs(self) -> list[str]:
        return self.conf.reqs if isinstance(self.conf.reqs, list) else [self.conf.reqs]

    @functools.cached_property
    def lock_files(self) -> list[str]:
        return self.conf.lock if isinstance(self.conf.lock, list) else [self.conf.lock]

    @functools.cached_property
    def environ(self) -> dict[str, str]:
        return os.environ  # type: ignore

    @functools.cached_property
    def dir(self) -> pathlib.Path:
        raise NotImplementedError

    @functools.cached_property
    def rel_dir(self) -> pathlib.Path:
        return self.dir

    @functools.cached_property
    def default_lock_file(self) -> str:
        raise NotImplementedError

    @functools.cached_property
    def lock_file(self) -> str:
        if len(self.lock_files) > 1:
            raise qik.errors.MultipleLocksFound(
                f'Multiple lock files found for "{self.name}" venv.'
            )

        return self.default_lock_file

    @functools.cached_property
    def rel_lock_file(self) -> str:
        return str(pathlib.Path(self.lock_file).relative_to(qik.conf.root()))


class Active(Venv, frozen=True, dict=True):
    """
    The active virtual environment.
    """

    conf: qik.conf.ActiveVenv

    @functools.cached_property
    def dir(self) -> pathlib.Path:
        return pathlib.Path(sysconfig.get_path("purelib"))


class UV(Venv, frozen=True, dict=True):
    """
    TODO: Move this Venv definition into qik.uv.venv module
    once we have a plugin system in place.
    """

    conf: qik.conf.UVVenv

    @functools.cached_property
    def default_lock_file(self) -> str:
        return str(
            qik.conf.pub_work_dir()
            / "artifacts"
            / qik.uv.cmd.lock_cmd_name()
            / f"requirements-{self.name}-lock.txt"
        )

    @functools.cached_property
    def lock_files(self) -> list[str]:
        if not self.conf.lock:
            return [self.default_lock_file]
        else:
            return super().lock_files

    @functools.cached_property
    def environ(self) -> dict[str, str]:
        return os.environ | {
            "VIRTUAL_ENV": str(self.dir),
            "PATH": f"{self.dir}/bin:{os.environ['PATH']}",
        }

    @functools.cached_property
    def dir(self) -> pathlib.Path:
        return qik.conf.priv_work_dir() / "venv" / self.name


def factory(name: str, *, conf: qik.conf.Venv | None) -> Venv:
    if isinstance(conf, qik.conf.ActiveVenv):
        return Active(name=name, conf=conf)
    elif isinstance(conf, qik.conf.UVVenv):
        return UV(name=name, conf=conf)
    elif conf is None:
        return Active(name=name, conf=qik.conf.ActiveVenv())
    else:
        raise qik.errors.VenvNotFound(f'Venv named "{name}" not configured in qik.venvs.')
