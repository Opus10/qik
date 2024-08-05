"""Qik project and configuration loading."""

from __future__ import annotations

import functools
import importlib.util
import os.path
import pathlib
import sys
from typing import Any, Literal, TypeAlias, TypeVar

import msgspec.structs
import msgspec.toml

import qik.unset

CtxNamespace: TypeAlias = Literal["qik", "project", "modules", "plugins"]
VarType: TypeAlias = str | bool | int
VAR_T = TypeVar("VAR_T", str, bool, int, None)
CacheBackend: TypeAlias = Literal["s3"]
CacheWhen: TypeAlias = Literal["success", "failed", "finished"]
CacheStatus: TypeAlias = Literal["warm", "code"]


class Base(
    msgspec.Struct,
    frozen=True,
    omit_defaults=True,
    forbid_unknown_fields=True,
    rename="kebab",
    dict=True,
):
    pass


class BaseDep(Base, frozen=True):
    pass


class GlobDep(BaseDep, tag="glob", frozen=True):
    pattern: str


class ConstDep(BaseDep, tag="const", frozen=True):
    val: str


class ValDep(BaseDep, tag="val", frozen=True):
    key: str
    file: str


class CmdDep(BaseDep, tag="command", frozen=True):
    name: str
    strict: bool = False
    isolated: bool | qik.unset.UnsetType = qik.unset.UNSET


class DistDep(BaseDep, tag="dist", frozen=True):
    name: str


class ModuleDep(BaseDep, tag="module", frozen=True):
    name: str


DepType: TypeAlias = str | GlobDep | CmdDep | DistDep | ModuleDep | ConstDep


class CmdConf(Base, frozen=True):
    exec: str = ""
    deps: list[DepType] = []
    artifacts: list[str] = []
    cache: str | qik.unset.UnsetType = qik.unset.UNSET
    cache_when: CacheWhen | qik.unset.UnsetType = qik.unset.UNSET
    factory: str = ""


class Var(Base, frozen=True):
    name: str
    type: Literal["str", "int", "bool"] = "str"
    default: VarType | qik.unset.UnsetType = qik.unset.UNSET
    required: bool = True

    def __post_init__(self):
        if not self.required and self.default is qik.unset.UNSET:
            msgspec.structs.force_setattr(self, "default", None)

    @property
    def py_type(self) -> type[VarType]:
        if self.required:
            return __builtins__[self.type]
        else:
            return __builtins__[self.type] | None


class ModuleConf(Base, frozen=True):
    vars: list[str | Var] = []
    commands: dict[str, CmdConf] = {}

    @functools.cached_property
    def vars_dict(self) -> dict[str, Var]:
        return dict((v, Var(v)) if isinstance(v, str) else (v.name, v) for v in self.vars)


class ModulePath(Base, frozen=True):
    name: str
    path: str

    @functools.cached_property
    def file_path(self) -> pathlib.Path:
        return root() / self.path.replace(".", os.path.sep)

    @functools.cached_property
    def conf(self) -> ModuleConf:
        try:
            return msgspec.toml.decode(
                (self.file_path / "qik.toml").read_bytes(),
                type=ModuleConf,
            )
        except FileNotFoundError:
            return ModuleConf()


class PluginPath(ModulePath, frozen=True):
    @functools.cached_property
    def file_path(self) -> pathlib.Path:
        spec = importlib.util.find_spec(self.path)
        if not spec or not spec.origin:
            raise RuntimeError(f'Could not import plugin "{self.name}"')

        return pathlib.Path(spec.origin).parent


class Env(Base, frozen=True):
    lock_file: str | list[str] = []


class Graph(Base, frozen=True):
    include_type_checking: bool = True
    include_dists: bool = True


class Cache(Base, frozen=True, tag_field="type"):
    pass


class S3Cache(Cache, frozen=True, tag="s3"):
    bucket: str
    prefix: str = ""
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None


class ProjectConf(ModuleConf, frozen=True):
    modules: list[str | ModulePath] = []
    plugins: list[str | PluginPath] = []
    deps: list[DepType] = []
    ctx: dict[str, dict[CtxNamespace, dict[str, Any]]] = {}
    venvs: dict[str, Env] = {}
    caches: dict[str, S3Cache] = {}
    graph: Graph = msgspec.field(default_factory=Graph)

    @functools.cached_property
    def modules_by_name(self) -> dict[str, ModulePath]:
        return dict(
            (m, ModulePath(m, m)) if isinstance(m, str) else (m.name, m) for m in self.modules
        )

    @functools.cached_property
    def modules_by_path(self) -> dict[str, ModulePath]:
        return {m.path: m for m in self.modules_by_name.values()}

    @functools.cached_property
    def plugins_by_name(self) -> dict[str, PluginPath]:
        return dict(
            (p, PluginPath(p, p)) if isinstance(p, str) else (p.name, p) for p in self.plugins
        )

    @functools.cached_property
    def plugins_by_path(self) -> dict[str, PluginPath]:
        return {p.path: p for p in self.plugins_by_name.values()}


class PyprojectTool(msgspec.Struct):
    qik: ProjectConf | None = None


class Pyproject(msgspec.Struct, omit_defaults=True):
    tool: PyprojectTool | None = None


@functools.cache
def _project_conf() -> tuple[ProjectConf, pathlib.Path]:
    """Return the project configuration and file."""
    cwd = pathlib.Path.cwd()
    qik_toml: pathlib.Path | None = None

    for directory in (cwd, *cwd.parents):
        if (directory / "qik.toml").is_file():
            qik_toml = directory / "qik.toml"

        if (
            has_pyproject := (directory / "pyproject.toml").is_file()
            or (directory / ".git").is_dir()
        ):
            if qik_toml and qik_toml.parent == directory:
                # qik.toml is at the root. Use qik.toml
                return msgspec.toml.decode(qik_toml.read_bytes(), type=ProjectConf), qik_toml
            elif has_pyproject:
                location = directory / "pyproject.toml"
                pyproject = msgspec.toml.decode(location.read_bytes(), type=Pyproject)
                if pyproject.tool and pyproject.tool.qik:
                    return pyproject.tool.qik, location
                elif qik_toml:  # qik.toml was found but not at root
                    return msgspec.toml.decode(qik_toml.read_bytes(), type=ProjectConf), qik_toml

            break

    raise RuntimeError("Could not locate qik configuration in qik.toml or pyproject.toml.")


@functools.cache
def project() -> ProjectConf:
    """Get project-level configuration."""
    sys.path.append(str(root()))
    return _project_conf()[0]


@functools.cache
def path_to_name(path: str) -> str:
    """Given a full path, return the module or plugin name."""
    proj = project()
    if path in proj.modules_by_path:
        return proj.modules_by_path[path].name
    elif path in proj.plugins_by_path:
        return proj.plugins_by_path[path].name
    else:
        raise KeyError(f'No configured module or plugin with path "{path}".')


@functools.cache
def module(name: str) -> ModuleConf:
    """Get module configuration."""
    proj = project()
    if name not in proj.modules_by_name:
        raise KeyError(f'Module "{name}" not configured in {location().name}.')

    return proj.modules_by_name[name].conf


def plugin(name: str) -> ModuleConf:
    """Get plugin configuration."""
    proj = project()
    if name not in proj.plugins_by_name:
        raise KeyError(f'Plugin "{name}" not configured in {location().name}.')

    return proj.plugins_by_name[name].conf


@functools.cache
def get(name: str | None = None) -> ModuleConf:
    """Get configuration for a given module, plugin, or project."""
    if not name:
        return project()
    else:
        try:
            return module(name)
        except KeyError:
            try:
                return plugin(name)
            except KeyError:
                raise KeyError(f'Module or plugin "{name}" not configured in {location().name}.')  # noqa: B904


@functools.cache
def uri_parts(uri: str) -> tuple[str | None, str]:
    """Return the module and name of a URI."""
    return (None, uri) if "." not in uri else tuple(uri.rsplit(".", 1))  # type: ignore


@functools.cache
def command(uri: str) -> CmdConf:
    """Get configuration for a command."""
    module, name = uri_parts(uri)
    conf = get(module)
    if name not in conf.commands:
        raise KeyError(f'Command "{uri}" not configured.')

    return conf.commands[name]


@functools.cache
def root() -> pathlib.Path:
    """Get the absolute root project directory."""
    return _project_conf()[1].parent


@functools.cache
def priv_work_dir(relative: bool = False) -> pathlib.Path:
    """Get the private work directory."""
    return root() / "._qik" if not relative else pathlib.Path("._qik")


@functools.cache
def pub_work_dir(relative: bool = False) -> pathlib.Path:
    """Get the public work directory."""
    return root() / ".qik" if not relative else pathlib.Path(".qik")


@functools.cache
def location() -> pathlib.Path:
    """Get the root configuration file."""
    return _project_conf()[1]
