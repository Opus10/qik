from __future__ import annotations

import collections
import functools
import importlib.metadata
import inspect
import os
import pathlib
import re
import sysconfig
import threading
from typing import Iterator

import msgspec

import qik.cmd
import qik.conf
import qik.dep
import qik.errors
import qik.file
import qik.func
import qik.hash


# From jaraco.functools 3.3
def _pass_none(func):
    @functools.wraps(func)
    def wrapper(param, *args, **kwargs):
        if param is not None:
            return func(param, *args, **kwargs)

    return wrapper


# copied from more_itertools 8.8
def _always_iterable(obj, base_type=(str, bytes)):
    if obj is None:
        return iter(())

    if (base_type is not None) and isinstance(obj, base_type):
        return iter((obj,))

    try:
        return iter(obj)
    except TypeError:
        return iter((obj,))


def _top_level_declared(dist):
    return (dist.read_text("top_level.txt") or "").split()


def _top_level_inferred(dist):
    opt_names = {
        f.parts[0] if len(f.parts) > 1 else inspect.getmodulename(f)
        for f in _always_iterable(dist.files)
    }

    @_pass_none
    def importable_name(name):
        return "." not in name

    return filter(importable_name, opt_names)


@qik.func.cache
def _normalize_pydist_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower().replace("-", "_")


@qik.func.cache
def _pydist_version_overrides() -> dict[str, str]:
    project_conf = qik.conf.project()
    base = collections.defaultdict(str) if project_conf.ignore_missing_pydists else {}
    return base | {
        _normalize_pydist_name(name): version
        for name, version in project_conf.pydist_versions.items()
    }


class PackagesDistributions(msgspec.Struct):
    venv_hash: str
    packages_distributions: dict[str, list[str]]


class Venv(msgspec.Struct, frozen=True, dict=True):
    name: str
    conf: qik.conf.Venv

    def __post_init__(self):
        self.__dict__["_packages_distributions_lock"] = threading.Lock()
        self.__dict__["_packages_distributions"] = (None, None)

    def distributions(self, **kwargs) -> Iterator[importlib.metadata.Distribution]:
        return importlib.metadata.distributions(path=[str(self.site_packages_dir)], **kwargs)  # type: ignore

    @property
    def alias(self) -> str:
        return f'"{self.name}" space'

    def version(self, name: str) -> str:
        try:
            return next(self.distributions(name=name)).version
        except StopIteration:
            try:
                return _pydist_version_overrides()[_normalize_pydist_name(name)]
            except KeyError as exc:
                raise qik.errors.DistributionNotFound(
                    f'Distribution "{name}" not found in {self.alias}.'
                ) from exc

    def packages_distributions(self) -> dict[str, list[str]]:
        """Obtain a mapping of modules to their associated python distributions.

        This is an expensive command, so use an underlying cache when possible.
        """
        venv_contents = set(os.listdir(self.site_packages_dir)) - {"__pycache__"}
        venv_hash = qik.hash.strs(*sorted(venv_contents))
        with self.__dict__["_packages_distributions_lock"]:
            if self.__dict__["_packages_distributions"][0] != venv_hash:
                pygraph_conf = qik.conf.project().pygraph
                cache_path = (
                    qik.conf.priv_work_dir()
                    / "venv"
                    / ".packages_distributions"
                    / f"{self.name}.json"
                )
                overrides = (
                    {}
                    if not pygraph_conf.ignore_missing_module_pydists
                    else collections.defaultdict(lambda: [""])
                )
                overrides |= {
                    module: [dist] for module, dist in pygraph_conf.module_pydists.items()
                }
                try:
                    cached_val = msgspec.json.decode(
                        cache_path.read_bytes(), type=PackagesDistributions
                    )
                    if cached_val.venv_hash == venv_hash:
                        return overrides | cached_val.packages_distributions
                except FileNotFoundError:
                    pass

                pkg_to_dist = collections.defaultdict(list)
                for dist in self.distributions():
                    for pkg in _top_level_declared(dist) or _top_level_inferred(dist):
                        pkg_to_dist[pkg].append(dist.metadata["Name"])

                cached_val = PackagesDistributions(
                    venv_hash=venv_hash,
                    packages_distributions=dict(pkg_to_dist),
                )
                qik.file.write(cache_path, msgspec.json.encode(cached_val))

                self.__dict__["_packages_distributions"] = (
                    venv_hash,
                    overrides | cached_val.packages_distributions,
                )

            return self.__dict__["_packages_distributions"][1]

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
    def site_packages_dir(self) -> pathlib.Path:
        raise NotImplementedError

    @qik.func.cached_property
    def lock(self) -> list[str]:
        return self.conf.lock if isinstance(self.conf.lock, list) else [self.conf.lock]

    @qik.func.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        raise NotImplementedError

    @qik.func.cached_property
    def glob_deps(self) -> set[str]:
        if isinstance(self.lock, list):
            return set(self.lock)
        elif isinstance(self.lock, str):
            return {self.lock}
        else:
            return set()

    @qik.func.cached_property
    def const_deps(self) -> set[str]:
        """Return the serialized venv as a constant dep."""
        return {msgspec.json.encode(self).decode()}

    @property
    def since_deps(self) -> set[str]:
        if not self.lock:
            raise qik.errors.LockFileNotFound(f"No lock configured for {self.alias}.")

        return set(self.lock)


class ActiveConf(qik.conf.Venv, frozen=True):
    reqs: str | list[str] = []

    @property
    def lock(self) -> str | list[str]:  # type: ignore
        lock = qik.conf.project().active_venv_lock
        return lock if isinstance(lock, list) else [lock]


class Active(Venv, frozen=True, dict=True):
    """
    The active virtual environment.
    """

    conf: ActiveConf

    @property
    def alias(self) -> str:
        return "active virtual environment"

    @property
    def dir(self) -> pathlib.Path:
        return pathlib.Path(sysconfig.get_path("data"))

    @property
    def site_packages_dir(self) -> pathlib.Path:
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
        import qik.uv.cmd as uv_cmd

        return str(
            qik.conf.pub_work_dir()
            / "artifacts"
            / uv_cmd.lock_cmd_name()
            / f"requirements-{self.name}-lock.txt"
        )

    @qik.func.cached_property
    def lock(self) -> list[str]:
        super_lock = super().lock
        if len(super_lock) > 1:
            raise qik.errors.UVMultipleLocks(
                f"Cannot have more than one lock file for {self.alias}."
            )

        return [self.default_lock] if not super_lock else super_lock

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
        import qik.uv.cmd as uv_cmd

        return {
            runnable.name: qik.dep.Runnable(name=runnable.name, obj=runnable, strict=True)
            for runnable in qik.cmd.load(
                uv_cmd.install_cmd_name(), venv=self.name
            ).runnables.values()
        }


_ACTIVE: Active = Active(name=".active", conf=ActiveConf())


def active() -> Active:
    """Return the active venv."""
    return _ACTIVE


def factory(name: str, *, conf: qik.conf.Venv) -> Venv:
    if isinstance(conf, qik.conf.UVVenv):
        return UV(name=name, conf=conf)
    else:
        raise AssertionError(f'Unexpected venv conf type "{conf.__class__}".')
