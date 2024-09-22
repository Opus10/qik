"""Qik project and configuration loading."""

from __future__ import annotations

import importlib
import importlib.util
import os.path
import pathlib
import sys
import operator
from types import UnionType
from typing import Any, Literal, TypeAlias, TypeVar, Union

import msgspec.structs
import msgspec.toml

import qik.conf
import qik.errors
import qik.func
import qik.unset

CtxNamespace: TypeAlias = Literal["qik", "project", "modules", "plugins"]
VarType: TypeAlias = str | bool | int
VAR_T = TypeVar("VAR_T", str, bool, int, None)
CacheWhen: TypeAlias = Literal["success", "failed", "finished"]
CacheStatus: TypeAlias = Literal["warm", "code"]


# Dynamic config classes and objects registered by plugins
_PLUGIN_CACHE_TYPES: dict[str, tuple[type[BaseCache], str]] = {}
_PLUGIN_VENV_TYPES: dict[str, tuple[type[BaseVenv], str]] = {}
_PLUGIN_CMDS: list[Cmd] = []


def register_cache_type(cache_type: type[BaseCache], factory: str) -> None:
    _PLUGIN_CACHE_TYPES[str(cache_type.__struct_config__.tag)] = (cache_type, factory)


def register_venv_type(venv_type: type[BaseVenv], factory: str) -> None:
    _PLUGIN_VENV_TYPES[str(venv_type.__struct_config__.tag)] = (venv_type, factory)


def register_cmd(cmd: Cmd) -> None:
    _PLUGIN_CMDS.append(cmd)


def get_cache_type_factory(conf: BaseCache) -> str:
    if entry := _PLUGIN_CACHE_TYPES.get(str(conf.__struct_config__.tag)):
        return entry[1]
    else:
        raise qik.errors.InvalidCacheType(f'Cache type "{conf.__struct_config__.tag}" not provided by any plugin.')


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


class Cmd(Base, frozen=True):
    exec: str = ""
    deps: list[DepType] = []
    artifacts: list[str] = []
    cache: str | qik.unset.UnsetType = qik.unset.UNSET
    cache_when: CacheWhen | qik.unset.UnsetType = qik.unset.UNSET
    factory: str = ""
    hidden: bool = False
    space: str | qik.unset.UnsetType = qik.unset.UNSET


class Var(Base, frozen=True):
    name: str
    type: Literal["str", "int", "bool"] = "str"
    default: VarType | qik.unset.UnsetType = qik.unset.UNSET
    required: bool = True

    def __post_init__(self):
        if not self.required and isinstance(self.default, qik.unset.UnsetType):
            msgspec.structs.force_setattr(self, "default", None)

    @property
    def py_type(self) -> type | UnionType:
        if self.required:
            return __builtins__[self.type]
        else:
            return __builtins__[self.type] | None


class ModuleOrPlugin(Base, frozen=True):
    vars: list[str | Var] = []
    commands: dict[str, Cmd] = {}

    @qik.func.cached_property
    def vars_dict(self) -> dict[str, Var]:
        return dict((v, Var(v)) if isinstance(v, str) else (v.name, v) for v in self.vars)


class BaseLocator(Base, frozen=True):
    name: str

    @qik.func.cached_property
    def dir(self) -> pathlib.Path:
        raise NotImplementedError

    @qik.func.cached_property
    def pyimport(self) -> str:
        raise NotImplementedError

    @qik.func.cached_property
    def conf(self) -> ModuleOrPlugin:
        try:
            return msgspec.toml.decode(
                (self.dir / "qik.toml").read_bytes(),
                type=ModuleOrPlugin,
            )
        except FileNotFoundError:
            return ModuleOrPlugin()


class ModuleLocator(BaseLocator, frozen=True):
    path: str

    @qik.func.cached_property
    def pyimport(self) -> str:
        return self.path.replace("/", ".")

    @qik.func.cached_property
    def dir(self) -> pathlib.Path:
        # TODO: While this handles most windows paths, it does not handle literal '/'
        # in paths that are escaped (e.g. my\/file/path)
        return pathlib.Path(self.path.replace("/", os.path.sep))


class PluginLocator(BaseLocator, frozen=True):
    pyimport: str  # type: ignore

    @qik.func.cached_property
    def dir(self) -> pathlib.Path:
        spec = importlib.util.find_spec(self.pyimport)
        if not spec or not spec.origin:
            raise qik.errors.PluginImport(f'Could not import plugin "{self.name}"')

        return pathlib.Path(spec.origin).parent


class BaseVenv(Base, frozen=True, tag_field="type"):
    reqs: str | list[str]
    lock: str | list[str] = []


class UVVenv(BaseVenv, frozen=True, tag="uv"):
    python: str | None = None


class Pygraph(Base, frozen=True):
    ignore_type_checking: bool = False
    ignore_pydists: bool = False
    ignore_missing_module_pydists: bool = False
    module_pydists: dict[str, str] = {}


class BaseCache(Base, frozen=True, tag_field="type"):
    pass


class Space(Base, frozen=True):
    root: str | None = None
    modules: list[str | ModuleLocator] = []
    fence: list[str] = []
    venv: str | BaseVenv | None = None

    @qik.func.cached_property
    def modules_by_name(self) -> dict[str, ModuleLocator]:
        module_locators = (
            ModuleLocator(name=m, path=m) if isinstance(m, str) else m for m in self.modules
        )
        return {m.name: m for m in module_locators}

    @qik.func.cached_property
    def modules_by_path(self) -> dict[str, ModuleLocator]:
        return {m.path: m for m in self.modules_by_name.values()}


class BaseProject(ModuleOrPlugin, frozen=True):
    plugins: list[str | PluginLocator] = []
    deps: list[DepType] = []
    ctx: dict[str, dict[CtxNamespace, dict[str, Any]]] = {}
    venvs: dict[str, BaseVenv] = {}
    caches: dict[str, BaseCache] = {}
    spaces: dict[str, Space] = {}
    pygraph: Pygraph = msgspec.field(default_factory=Pygraph)
    pydist_versions: dict[str, str] = {}
    ignore_missing_pydists: bool = False
    active_venv_lock: str | list[str] = []

    @qik.func.cached_property
    def modules_by_name(self) -> dict[str, ModuleLocator]:
        return {
            name: locator
            for space in self.spaces.values()
            for name, locator in space.modules_by_name.items()
        }

    @qik.func.cached_property
    def modules_by_path(self) -> dict[str, ModuleLocator]:
        return {m.path: m for m in self.modules_by_name.values()}

    @qik.func.cached_property
    def plugins_by_name(self) -> dict[str, PluginLocator]:
        plugin_locators = (
            PluginLocator(name=p, pyimport=p) if isinstance(p, str) else p for p in self.plugins
        )
        return {p.name: p for p in plugin_locators}

    @qik.func.cached_property
    def plugins_by_pyimport(self) -> dict[str, PluginLocator]:
        return {p.pyimport: p for p in self.plugins_by_name.values()}
    

class ProjectPlugins(msgspec.Struct, frozen=True):
    """Parses the root qik.toml file for plugins.

    Allows us to dynamically determine the structure of the config based on installed
    plugins.
    """
    plugins: list[str | PluginLocator] = []


def _load_plugins(conf: ProjectPlugins) -> None:
    """Load plugins and return the Project configuration."""
    for plugin in conf.plugins:
        pyimport = plugin if isinstance(plugin, str) else plugin.pyimport

        try:
            importlib.import_module(f"{pyimport}.qikplugin")
        except ModuleNotFoundError as e:
            # A ModuleNotFoundError is raised if the plugin is not installed
            # or if the plugin itself has issues importing code. Distinguish
            # between the two.
            if pyimport in e.args[0]:
                raise qik.errors.PluginNotFound(
                    f"Plugin '{pyimport}' could not be imported. "
                    f"Make sure it's installed and has a 'qikplugin' module."
                )
            else:
                # TODO: Show that this is an unexpected error. Currently CLI
                # users get a raw stack trace.
                raise


def _parse_project_config(contents: bytes) -> BaseProject:
    """Dynamically generate a Project config class based on installed plugins."""
    class DynamicSpace(Space, frozen=True):
        venv: str | UVVenv | None = None

    # Must register as part of the global namespace in order for msgspec to
    # recognize dynamic nested type.
    globals()['DynamicSpace'] = DynamicSpace
    globals()['DynamicCacheTypes'] = Union[(BaseCache, *(cls for cls, _ in _PLUGIN_CACHE_TYPES.values()))]

    class Project(BaseProject, frozen=True):
        venvs: dict[str, UVVenv] = {}  # type: ignore
        caches: dict[str, DynamicCacheTypes] = {}  # type: ignore
        spaces: dict[str, DynamicSpace] = {}  # type: ignore

    return msgspec.toml.decode(contents, type=Project)


@qik.func.cache
def _project() -> tuple[BaseProject, pathlib.Path]:
    """Return the project configuration and file."""
    cwd = pathlib.Path.cwd()
    qik_toml: pathlib.Path | None = None

    for directory in (cwd, *cwd.parents):
        if (directory / "qik.toml").is_file():
            qik_toml = directory / "qik.toml"

        if (directory / ".git").is_dir():
            break

    if qik_toml:
        contents = qik_toml.read_bytes()
        _load_plugins(msgspec.toml.decode(contents, type=ProjectPlugins))
        return _parse_project_config(contents), qik_toml
    else:
        raise qik.errors.ConfigNotFound("Could not locate qik.toml configuration file.")


def project() -> BaseProject:
    sys.path.append(str(root()))
    return _project()[0]


@qik.func.cache
def module_locator(uri: str, *, by_path: bool = False) -> ModuleLocator:
    """Get module locator."""
    proj = project()
    lookup = proj.modules_by_path if by_path else proj.modules_by_name
    if uri not in lookup:
        raise qik.errors.ModuleNotFound(f'Module "{uri}" not configured in {location().name}.')

    return lookup[uri]


@qik.func.cache
def module(uri: str, *, by_path: bool = False) -> ModuleOrPlugin:
    """Get module configuration."""
    return module_locator(uri, by_path=by_path).conf


@qik.func.cache
def plugin_locator(uri: str, *, by_pyimport: bool = False) -> PluginLocator:
    """Get plugin locator."""
    proj = project()
    lookup = proj.plugins_by_pyimport if by_pyimport else proj.plugins_by_name
    if uri not in lookup:
        raise qik.errors.PluginNotFound(f'Plugin "{uri}" not configured in {location().name}.')

    return lookup[uri]


@qik.func.cache
def plugin(uri: str, by_pyimport: bool = False) -> ModuleOrPlugin:
    """Get plugin configuration."""
    return plugin_locator(uri, by_pyimport=by_pyimport).conf


@qik.func.cache
def get(name: str | None = None) -> ModuleOrPlugin:
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


@qik.func.cache
def uri_parts(uri: str) -> tuple[str | None, str]:
    """Return the module and name of a URI."""
    return (None, uri) if "." not in uri else tuple(uri.rsplit(".", 1))  # type: ignore


@qik.func.cache
def command(uri: str) -> Cmd:
    """Get configuration for a command."""
    module, name = uri_parts(uri)
    conf = get(module)
    if name not in conf.commands:
        raise qik.errors.CommandNotFound(f'Command "{uri}" not configured.')

    return conf.commands[name]


@qik.func.cache
def space(name: str = "default") -> Space:
    """Get configuration for a space."""
    proj = project()
    if name != "default" and name not in proj.spaces:
        raise qik.errors.SpaceNotFound(f'Space "{name}" not configured.')

    return proj.spaces.get(name, Space(venv="default"))


@qik.func.cache
def root() -> pathlib.Path:
    """Get the absolute root project directory."""
    return _project()[1].parent


@qik.func.cache
def priv_work_dir(abs: bool = False) -> pathlib.Path:
    """Get the private work directory."""
    return root() / "._qik" if abs else pathlib.Path("._qik")


@qik.func.cache
def pub_work_dir(abs: bool = False) -> pathlib.Path:
    """Get the public work directory."""
    return root() / ".qik" if abs else pathlib.Path(".qik")


@qik.func.cache
def location() -> pathlib.Path:
    """Get the root configuration file."""
    return _project()[1]
