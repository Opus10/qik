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
    base = collections.defaultdict(str) if project_conf.pydist.ignore_missing else {}
    return base | {
        _normalize_pydist_name(name): version
        for name, version in project_conf.pydist.versions.items()
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

    # TODO: Consider caching distributions and all versions in a similar manner as
    # the packages_distributions cache.
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
                pydist_conf = qik.conf.project().pydist
                cache_path = (
                    qik.conf.priv_work_dir()
                    / "venv"
                    / ".packages_distributions"
                    / f"{self.name}.json"
                )
                overrides = (
                    {}
                    if not pydist_conf.ignore_missing_modules
                    else collections.defaultdict(lambda: [""])
                )
                overrides |= {module: [dist] for module, dist in pydist_conf.modules.items()}
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
    def lock(self) -> str | None:
        return self.conf.lock

    @qik.func.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        raise NotImplementedError

    @qik.func.cached_property
    def glob_deps(self) -> set[str]:
        return {self.lock} if self.lock else set(self.reqs)

    @qik.func.cached_property
    def const_deps(self) -> set[str]:
        """Return the serialized venv as a constant dep."""
        return {msgspec.json.encode(self).decode()}

    @property
    def since_deps(self) -> set[str]:
        return set().union(self.reqs, [self.lock] if self.lock else [])


class Active(Venv, frozen=True, dict=True):
    """
    The active virtual environment.
    """

    conf: qik.conf.ActiveVenv

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


_ACTIVE: Active = Active(name=".active", conf=qik.conf.ActiveVenv())


def active() -> Active:
    """Return the active venv."""
    return _ACTIVE
