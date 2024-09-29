from __future__ import annotations

import pathlib
import pkgutil
import re
from typing import TYPE_CHECKING

import msgspec

import qik.cmd
import qik.conf
import qik.ctx
import qik.errors
import qik.file
import qik.func
import qik.hash
import qik.unset

if TYPE_CHECKING:
    import qik.runnable


@qik.func.cache
def _normalize_pydist_name(pydist: str) -> str:
    pydist = pydist.lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", pydist)


class Runnable(msgspec.Struct, frozen=True):
    """A runnable included by a dependency."""

    name: str
    obj: qik.runnable.Runnable
    strict: bool = False
    isolated: bool | qik.unset.UnsetType = qik.unset.UNSET


class Dep(msgspec.Struct, frozen=True, tag=True, dict=True):
    """A base dependency."""

    val: str

    def __str__(self) -> str:
        return self.val

    @qik.func.cached_property
    def runnables(self) -> list[Runnable]:
        """Return any runnables of the dependency."""
        return []

    @qik.func.cached_property
    def globs(self) -> list[str]:
        """Return any glob patterns of the dependency."""
        return []

    @qik.func.cached_property
    def pydists(self) -> list[str]:
        """Return any pydists of the dependency."""
        return []

    @qik.func.cached_property
    def vals(self) -> list[str]:
        """Return any vals of the dependency."""
        return []

    @qik.func.cached_property
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

    @qik.func.cached_property
    def since(self) -> list[str]:
        """Return any globs used for --since option.

        When using --since, we need to estimate which commands need to
        be re-executed based on git changes. For deps such as
        pydists or vals that aren't directly tied to git, we return globs
        that encapsulate those changes (lock files, parent files, etc).
        """
        return self.watch


def factory(
    conf: qik.conf.Dep | str | pathlib.Path,
    module: qik.conf.ModuleLocator | None = None,
    space: str | None = None,
) -> Dep:
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
        case qik.conf.CmdDep():
            return Cmd(_fmt(conf.name), strict=conf.strict, isolated=conf.isolated)
        case qik.conf.ConstDep():
            return Const(_fmt(conf.val))
        case qik.conf.LoadDep():
            return Load(_fmt(conf.path), default=conf.default)
        case other:
            factory = qik.conf.get_type_factory(other)
            return pkgutil.resolve_name(factory)(conf, module=module, space=space)


class Glob(Dep, frozen=True):
    """A dependent glob pattern"""

    @qik.func.cached_property
    def globs(self) -> list[str]:
        return [self.val]


class Val(Dep, frozen=True):
    """A value from a file."""

    file: str

    @property
    def vals(self) -> list[str]:  # type: ignore
        # This dependency is still experimental and only used by qik.pygraph.
        raise NotImplementedError

    @qik.func.cached_property
    def watch(self) -> list[str]:
        return [self.file]


class BaseCmd(Dep, frozen=True):
    strict: bool = False
    isolated: bool | qik.unset.UnsetType = qik.unset.UNSET
    args: dict[str, str | None] = {}

    def get_cmd_name(self) -> str:
        raise NotImplementedError

    def get_cmd_args(self) -> dict[str, str | None]:
        return self.args

    @qik.func.cached_property
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


class Pydist(Dep, frozen=True):
    """A python distribution dependency."""

    @property
    def normalized(self) -> str:
        return _normalize_pydist_name(self.val)

    @qik.func.cached_property
    def pydists(self) -> list[str]:
        return [self.val]


class Const(Dep, frozen=True):
    """A constant value."""

    @qik.func.cached_property
    def since(self) -> list[str]:
        return ["*qik.toml"]


class Load(Dep, frozen=True):
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


class Serialized(msgspec.Struct, frozen=True, omit_defaults=True):
    """A serialized representation of dependencies, meant to be loaded from a file."""

    globs: list[str] = []
    pydists: list[str] = []
    hash: str | None = None


@qik.func.cache
def base() -> list[Dep]:
    """The base dependencies for the project."""
    return [factory(dep) for dep in qik.conf.project().base.deps]
