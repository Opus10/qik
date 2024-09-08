from __future__ import annotations

import functools
import pathlib
import re
from typing import TYPE_CHECKING, ClassVar

import msgspec

import qik.cmd
import qik.conf
import qik.ctx
import qik.errors
import qik.file
import qik.hash
import qik.unset
import qik.venv

if TYPE_CHECKING:
    import qik.pygraph.cmd as pygraph_cmd
    import qik.runnable
else:
    import qik.lazy

    pygraph_cmd = qik.lazy.module("qik.pygraph.cmd")


@functools.cache
def _normalize_pydist_name(pydist: str) -> str:
    pydist = pydist.lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", pydist)


class Runnable(msgspec.Struct, frozen=True):
    """A runnable included by a dependency."""

    name: str
    obj: qik.runnable.Runnable
    strict: bool = False
    isolated: bool | qik.unset.UnsetType = qik.unset.UNSET


class BaseDep(msgspec.Struct, frozen=True, tag=True, dict=True):
    """A base dependency."""

    val: str

    def __str__(self) -> str:
        return self.val

    @functools.cached_property
    def runnables(self) -> list[Runnable]:
        """Return any runnables of the dependency."""
        return []

    @functools.cached_property
    def globs(self) -> list[str]:
        """Return any glob patterns of the dependency."""
        return []

    @functools.cached_property
    def pydists(self) -> list[str]:
        """Return any pydists of the dependency."""
        return []

    @functools.cached_property
    def vals(self) -> list[str]:
        """Return any vals of the dependency."""
        return []

    @functools.cached_property
    def watch(self) -> list[str]:
        """Return any globs used for --watch option.

        When using --watch, we need to react to events based on file
        system changes. Similar to `since`, we return globs
        used by the watcher to determine changes. The main difference
        between `since` and `watch` is that the watcher has access to
        more than just git files (venv, etc). As a result, we don't
        need to react to as many files in the git repo, such as
        reacting based on a lock file change.
        """
        return self.globs

    @functools.cached_property
    def since(self) -> list[str]:
        """Return any globs used for --since option.

        When using --since, we need to estimate which commands need to
        be re-executed based on git changes. For deps such as
        pydists or vals that aren't directly tied to git, we return globs
        that encapsulate those changes (lock files, parent files, etc).
        """
        return self.watch


def factory(
    conf: qik.conf.BaseDep | str | pathlib.Path, module: qik.conf.ModuleLocator | None = None
) -> BaseDep:
    """A factory for creating dependencies from a configuration."""

    def _fmt(val: str) -> str:
        return qik.ctx.format(val, module=module)

    match conf:
        case str() | pathlib.Path():
            return Glob(_fmt(str(conf)))
        case qik.conf.GlobDep():
            return Glob(_fmt(conf.pattern))
        case qik.conf.PydistDep():
            return Pydist(_fmt(conf.name))
        case qik.conf.ValDep():
            return Val(_fmt(conf.key), file=_fmt(conf.file))
        case qik.conf.PygraphDep():
            return Pygraph(_fmt(conf.pyimport))
        case qik.conf.CmdDep():
            return Cmd(_fmt(conf.name), strict=conf.strict, isolated=conf.isolated)
        case qik.conf.ConstDep():
            return Const(_fmt(conf.val))
        case qik.conf.LoadDep():
            return Load(_fmt(conf.path), default=conf.default)
        case other:
            raise AssertionError(f'Unexpected dep cls "{other}"')


class Glob(BaseDep, frozen=True):
    """A dependent glob pattern"""

    @functools.cached_property
    def globs(self) -> list[str]:
        return [self.val]


class Val(BaseDep, frozen=True):
    """A value from a file."""

    file: str

    @property
    def vals(self) -> list[str]:  # type: ignore
        # This dependency is still experimental and only used by qik.pygraph.
        raise NotImplementedError

    @functools.cached_property
    def watch(self) -> list[str]:
        return [self.file]


class BaseCmd(BaseDep, frozen=True):
    strict: bool = False
    isolated: bool | qik.unset.UnsetType = qik.unset.UNSET

    def get_cmd_name(self) -> str:
        raise NotImplementedError

    def get_cmd_args(self) -> dict[str, str]:
        return {}

    @functools.cached_property
    def runnables(self) -> list[Runnable]:
        """Return any runnables of the dependency."""
        return [
            Runnable(name=runnable.name, obj=runnable, strict=self.strict, isolated=self.isolated)
            for runnable in qik.cmd.load(
                self.get_cmd_name(), **self.get_cmd_args()
            ).runnables.values()
        ]


class Cmd(BaseCmd, frozen=True):
    """A dependent command."""

    def get_cmd_name(self) -> str:
        return self.val


class Pydist(BaseDep, frozen=True):
    """A python distribution dependency."""

    @property
    def normalized(self) -> str:
        return _normalize_pydist_name(self.val)

    @functools.cached_property
    def pydists(self) -> list[str]:
        return [self.val]

    @functools.cached_property
    def since(self) -> list[str]:
        venv = qik.venv.load()
        if not venv.lock_file:
            raise qik.errors.LockFileNotFound(
                "Must configure venv lock file (venvs.default.lock-file) when using --since on pydists."
            )

        return venv.lock_file


class Const(BaseDep, frozen=True):
    """A constant value."""

    @functools.cached_property
    def since(self) -> list[str]:
        return ["*qik.toml"]


class Pygraph(BaseCmd, frozen=True):
    """A python module and its associated imports."""

    strict: ClassVar[bool] = True  # type: ignore

    def get_cmd_name(self) -> str:
        return pygraph_cmd.lock_cmd_name()

    def get_cmd_args(self) -> dict[str, str]:
        return {"pyimport": self.val}

    @property
    def globs(self) -> list[str]:  # type: ignore
        return [str(pygraph_cmd.lock_path(self.val))]


class Load(BaseDep, frozen=True):
    """Load serialized dependencies from a file."""

    default: list[str] = []  # The default globs if the file doesn't exist

    def load(self) -> Serialized | None:
        """Get the loaded dependencies."""
        try:
            return msgspec.json.decode(pathlib.Path(self.val).read_bytes(), type=Serialized)
        except (FileNotFoundError, msgspec.DecodeError):
            return None

    @property
    def pydists(self) -> list[str]:  # type: ignore
        deps = self.load()
        return deps.pydists if deps else []

    @property
    def globs(self) -> list[str]:  # type: ignore
        deps = self.load()
        return deps.globs if deps else self.default


def store(
    path: pathlib.Path,
    *,
    globs: list[str] | None = None,
    pydists: list[str] | None = None,
    hash: bool = True,
) -> None:
    if hash:
        hash_val = Collection(*[*(globs or []), *[Pydist(val=pydist) for pydist in pydists or []]]).hash()
    else:
        hash_val = None

    qik.file.write(
        path, msgspec.json.encode(Serialized(globs=globs or [], pydists=pydists or [], hash=hash_val))
    )


class Serialized(msgspec.Struct, frozen=True, omit_defaults=True):
    """A serialized representation of dependencies, meant to be loaded from a file."""

    globs: list[str] = []
    pydists: list[str] = []
    hash: str | None = None


class Collection:
    """A filterable and hashable collection of dependencies."""

    def __init__(self, *deps: str | pathlib.Path | BaseDep, module: str | None = None):
        self._deps = [dep if isinstance(dep, BaseDep) else Glob(str(dep)) for dep in deps]
        self.module = module

    @property
    def globs(self) -> set[str]:
        return {glob for dep in self._deps for glob in dep.globs} | {
            artifact for runnable in self.runnables.values() for artifact in runnable.obj.artifacts
        }

    @functools.cached_property
    def consts(self) -> set[str]:
        return {dep.val for dep in self._deps if isinstance(dep, Const)}

    @functools.cached_property
    def watch(self) -> set[str]:
        return {glob for dep in self._deps for glob in dep.watch}

    @functools.cached_property
    def since(self) -> set[str]:
        return {glob for dep in self._deps for glob in dep.since}

    @property
    def vals(self) -> set[str]:
        return {val for dep in self._deps for val in dep.vals}

    @property
    def pydists(self) -> set[str]:
        return {pydist for dep in self._deps for pydist in dep.pydists}

    @property
    def runnables(self) -> dict[str, Runnable]:
        return {
            runnable.name: runnable
            for dep in self._deps
            for runnable in dep.runnables
            if not self.module or not runnable.obj.module or self.module == runnable.obj.module
        }

    @functools.cached_property
    def consts_hash(self) -> str:
        """Hash all consts."""
        return qik.hash.strs(*self.consts)

    def hash_vals(self) -> str:
        """Hash file values."""
        return qik.hash.strs(*self.vals)

    def hash_pydists(self) -> str:
        """Hash python distributions."""
        return qik.hash.pydists(*self.pydists)

    def hash_globs(self) -> str:
        """Hash glob pattern."""
        return qik.hash.globs(*self.globs)

    def hash(self) -> str:
        """The full hash."""
        return qik.hash.strs(
            self.consts_hash, self.hash_vals(), self.hash_globs(), self.hash_pydists()
        )


@functools.cache
def project_deps() -> list[BaseDep]:
    """The base dependencies for the project."""
    proj = qik.conf.project()
    return [factory(dep) for dep in proj.deps]
