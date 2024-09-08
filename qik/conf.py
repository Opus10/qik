"""Qik project and configuration loading."""

from __future__ import annotations

import functools
import importlib.util
import os.path
import pathlib
import sys
from types import UnionType
from typing import Any, Literal, TypeAlias, TypeVar

import msgspec.structs
import msgspec.toml

import qik.errors
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


class PydistDep(BaseDep, tag="pydist", frozen=True):
    name: str


class PygraphDep(BaseDep, tag="pygraph", frozen=True):
    pyimport: str


class LoadDep(BaseDep, tag="load", frozen=True):
    path: str
    default: list[str] = []


DepType: TypeAlias = str | GlobDep | CmdDep | PydistDep | PygraphDep | ConstDep | LoadDep


class CmdConf(Base, frozen=True):
    exec: str = ""
    deps: list[DepType] = []
    artifacts: list[str] = []
    cache: str | qik.unset.UnsetType = qik.unset.UNSET
    cache_when: CacheWhen | qik.unset.UnsetType = qik.unset.UNSET
    factory: str = ""
    hidden: bool = False


class Var(Base, frozen=True):
    name: str
    type: Literal["str", "int", "bool"] = "str"
    default: VarType | qik.unset.UnsetType = qik.unset.UNSET
    required: bool = True

    def __post_init__(self):
        if not self.required and self.default is qik.unset.UNSET:
            msgspec.structs.force_setattr(self, "default", None)

    @property
    def py_type(self) -> type | UnionType:
        if self.required:
            return __builtins__[self.type]
        else:
            return __builtins__[self.type] | None


class ModuleOrPluginConf(Base, frozen=True):
    vars: list[str | Var] = []
    commands: dict[str, CmdConf] = {}

    @functools.cached_property
    def vars_dict(self) -> dict[str, Var]:
        return dict((v, Var(v)) if isinstance(v, str) else (v.name, v) for v in self.vars)


class BaseLocator(Base, frozen=True):
    name: str

    @functools.cached_property
    def dir(self) -> pathlib.Path:
        raise NotImplementedError

    @functools.cached_property
    def pyimport(self) -> str:
        raise NotImplementedError

    @functools.cached_property
    def conf(self) -> ModuleOrPluginConf:
        try:
            return msgspec.toml.decode(
                (self.dir / "qik.toml").read_bytes(),
                type=ModuleOrPluginConf,
            )
        except FileNotFoundError:
            return ModuleOrPluginConf()


class ModuleLocator(BaseLocator, frozen=True):
    path: str

    @functools.cached_property
    def pyimport(self) -> str:
        return self.path.replace("/", ".")

    @functools.cached_property
    def dir(self) -> pathlib.Path:
        # TODO: While this handles most windows paths, it does not handle literal '/'
        # in paths that are escaped (e.g. my\/file/path)
        return root() / self.path.replace("/", os.path.sep)


class PluginLocator(BaseLocator, frozen=True):
    pyimport: str  # type: ignore

    @functools.cached_property
    def dir(self) -> pathlib.Path:
        spec = importlib.util.find_spec(self.pyimport)
        if not spec or not spec.origin:
            raise qik.errors.PluginImport(f'Could not import plugin "{self.name}"')

        return pathlib.Path(spec.origin).parent


class Venv(Base, frozen=True):
    lock_file: str | list[str] = []


class Pygraph(Base, frozen=True):
    ignore_type_checking: bool = False
    ignore_pydists: bool = False
    ignore_missing_module_pydists: bool = False
    module_pydists: dict[str, str] = {}


class Cache(Base, frozen=True, tag_field="type"):
    pass


class S3Cache(Cache, frozen=True, tag="s3"):
    bucket: str
    prefix: str = ""
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    endpoint_url: str | None = None


class ProjectConf(ModuleOrPluginConf, frozen=True):
    modules: list[str | ModuleLocator] = []
    plugins: list[str | PluginLocator] = []
    deps: list[DepType] = []
    ctx: dict[str, dict[CtxNamespace, dict[str, Any]]] = {}
    venvs: dict[str, Venv] = {}
    caches: dict[str, S3Cache] = {}
    pygraph: Pygraph = msgspec.field(default_factory=Pygraph)
    pydist_versions: dict[str, str] = {}
    ignore_missing_pydists: bool = False

    @functools.cached_property
    def modules_by_name(self) -> dict[str, ModuleLocator]:
        module_locators = (
            ModuleLocator(name=m.replace("/", "."), path=m) if isinstance(m, str) else m
            for m in self.modules
        )
        return {m.name: m for m in module_locators}

    @functools.cached_property
    def modules_by_path(self) -> dict[str, ModuleLocator]:
        return {m.path: m for m in self.modules_by_name.values()}

    @functools.cached_property
    def plugins_by_name(self) -> dict[str, PluginLocator]:
        plugin_locators = (
            PluginLocator(name=p, pyimport=p) if isinstance(p, str) else p for p in self.plugins
        )
        return {p.name: p for p in plugin_locators}

    @functools.cached_property
    def plugins_by_pyimport(self) -> dict[str, PluginLocator]:
        return {p.pyimport: p for p in self.plugins_by_name.values()}


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

    raise qik.errors.ConfigNotFound(
        "Could not locate qik configuration in qik.toml or pyproject.toml."
    )


@functools.cache
def project() -> ProjectConf:
    """Get project-level configuration."""
    sys.path.append(str(root()))
    return _project_conf()[0]


@functools.cache
def module_locator(uri: str, *, by_path: bool = False) -> ModuleLocator:
    """Get module locator."""
    proj = project()
    lookup = proj.modules_by_path if by_path else proj.modules_by_name
    if uri not in lookup:
        raise qik.errors.ModuleNotFound(f'Module "{uri}" not configured in {location().name}.')

    return lookup[uri]


@functools.cache
def module(uri: str, *, by_path: bool = False) -> ModuleOrPluginConf:
    """Get module configuration."""
    return module_locator(uri, by_path=by_path).conf


@functools.cache
def plugin_locator(uri: str, *, by_pyimport: bool = False) -> PluginLocator:
    """Get plugin locator."""
    proj = project()
    lookup = proj.plugins_by_pyimport if by_pyimport else proj.plugins_by_name
    if uri not in lookup:
        raise qik.errors.PluginNotFound(f'Plugin "{uri}" not configured in {location().name}.')

    return lookup[uri]


@functools.cache
def plugin(uri: str, by_pyimport: bool = False) -> ModuleOrPluginConf:
    """Get plugin configuration."""
    return plugin_locator(uri, by_pyimport=by_pyimport).conf


@functools.cache
def get(name: str | None = None) -> ModuleOrPluginConf:
    """Get configuration for a given module, plugin, or project."""
    if not name:
        return project()
    else:
        try:
            return module(name)
        except qik.errors.ModuleNotFound:
            try:
                return plugin(name)
            except qik.errors.PluginNotFound:
                raise qik.errors.ModuleOrPluginNotFound(
                    f'Module or plugin "{name}" not configured in {location().name}.'
                ) from None


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
        raise qik.errors.CommandNotFound(f'Command "{uri}" not configured.')

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
