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
    reqs: list[str] = []
    lock: list[str] = []

    @functools.cached_property
    def environ(self) -> dict[str, str]:
        return os.environ  # type: ignore

    @functools.cached_property
    def dir(self) -> pathlib.Path:
        return pathlib.Path(sysconfig.get_path("purelib"))

    @functools.cached_property
    def rel_dir(self) -> pathlib.Path:
        return self.dir

    @functools.cached_property
    def lock_file(self) -> str:
        # TODO: Do not return a default lock file here, instead require the user to
        # define it if they're not using a venv plugin
        raise NotImplementedError
    
    @functools.cached_property
    def rel_lock_file(self) -> str:
        return str(pathlib.Path(self.lock_file).relative_to(qik.conf.root()))
    
    @functools.cached_property
    def lock_files(self) -> list[str]:
        # TODO: Do not return a default lock file here, instead require the user to
        # define it if they're not using a venv plugin
        raise NotImplementedError


class UV(Venv, frozen=True, dict=True):
    """
    TODO: Move this Venv definition into qik.uv.venv module
    once we have a plugin system in place.
    """

    @functools.cached_property
    def environ(self) -> dict[str, str]:
        return os.environ | {
            "VIRTUAL_ENV": str(self.dir),
            "PATH": f"{self.dir}/bin:{os.environ['PATH']}",
        }

    @functools.cached_property
    def dir(self) -> pathlib.Path:
        return qik.conf.priv_work_dir() / "venv" / self.name

    @functools.cached_property
    def rel_dir(self) -> pathlib.Path:
        return self.dir.relative_to(qik.conf.root())

    @functools.cached_property
    def lock_files(self) -> list[str]:        
        if not self.lock:
            return [str(qik.conf.pub_work_dir() / "artifacts" / qik.uv.cmd.lock_cmd_name() / f"requirements-{self.name}-lock.txt")]
        else:
            return self.lock

    @functools.cached_property
    def lock_file(self) -> str:
        if len(self.lock_files) > 1:
            raise qik.errors.MultipleLocksFound(
                f'Multiple lock files found for "{self.name}" venv.'
            )
        
        return self.lock_files[0]


@functools.cache
def load(name: str = "default") -> Venv:
    """Load a virtual environment."""
    proj = qik.conf.project()
    if conf := proj.venvs.get(name):
        reqs = conf.reqs if isinstance(conf.reqs, list) else [conf.reqs]
        lock = conf.lock if isinstance(conf.lock, list) else [conf.lock]
        return UV(name=name, reqs=reqs, lock=lock)
    elif name == "default":
        return UV(name="default")
    else:
        raise qik.errors.VenvNotFound(f'Venv named "{name}" not configured in qik.venvs.')
