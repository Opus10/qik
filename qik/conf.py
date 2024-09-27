"""Qik project and configuration loading."""

from __future__ import annotations

import collections
import importlib.util
import os.path
import pathlib
import sys
from types import UnionType
from typing import Any, ClassVar, Literal, TypeAlias, TypeVar, Union

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


# Dynamic objects registered by plugins
_PLUGIN_TYPES: dict[str, dict[str, tuple[type[BasePluggable], str]]] = collections.defaultdict(
    dict
)
# Dynamic conf classes registered by plugins
_CONF_TYPES: dict[str, type[msgspec.Struct]] = {}


def register_type(plugin_type: type[BasePluggable], factory: str) -> None:
    _PLUGIN_TYPES[plugin_type.plugin_type_name][str(plugin_type.__struct_config__.tag)] = (
        plugin_type,
        factory,
    )


def register_conf(conf_type: type[msgspec.Struct], plugin_pyimport: str) -> None:
    _CONF_TYPES[plugin_pyimport] = conf_type


def get_type_factory(conf: BasePluggable) -> str:
    if entry := _PLUGIN_TYPES[conf.plugin_type_name].get(str(conf.__struct_config__.tag)):
        return entry[1]
    else:
        raise qik.errors.InvalidCacheType(
            f'{conf.plugin_type_name.title()} type "{conf.__struct_config__.tag}" not provided by any plugin.'
        )


class Base(
    msgspec.Struct,
    frozen=True,
    omit_defaults=True,
    forbid_unknown_fields=True,
    rename="kebab",
    dict=True,
):
    pass


class BasePluggable(Base, frozen=True):
    plugin_type_name: ClassVar[str]


class Dep(BasePluggable, frozen=True):
    plugin_type_name: ClassVar[str] = "dep"


class GlobDep(Dep, tag="glob", frozen=True):
    pattern: str


class ConstDep(Dep, tag="const", frozen=True):
    val: str


class ValDep(Dep, tag="val", frozen=True):
    key: str
    file: str


class CmdDep(Dep, tag="command", frozen=True):
    name: str
    strict: bool = False
    isolated: bool | qik.unset.UnsetType = qik.unset.UNSET


class PydistDep(Dep, tag="pydist", frozen=True):
    name: str


class LoadDep(Dep, tag="load", frozen=True):
    path: str
    default: list[str] = []


class Cmd(Base, frozen=True):
    exec: str = ""
    deps: list[str | Dep] = []
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
    def pytype(self) -> type | UnionType:
        if self.required:
            return __builtins__[self.type]
        else:
            return __builtins__[self.type] | None


class ModuleOrPlugin(Base, frozen=True):
    commands: dict[str, Cmd] = {}


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


class Venv(BasePluggable, frozen=True, tag_field="type"):
    plugin_type_name: ClassVar[str] = "venv"
    reqs: str | list[str]
    lock: str | None = None


class ActiveVenv(Venv, frozen=True, tag="active"):
    reqs: str | list[str] = []


class Cache(BasePluggable, frozen=True, tag_field="type"):
    plugin_type_name: ClassVar[str] = "cache"


class Space(Base, frozen=True):
    root: str | None = None
    modules: list[str | ModuleLocator] = []
    fence: list[str] = []
    venv: str | Venv | None = None

    @qik.func.cached_property
    def modules_by_name(self) -> dict[str, ModuleLocator]:
        module_locators = (
            ModuleLocator(name=m, path=m) if isinstance(m, str) else m for m in self.modules
        )
        return {m.name: m for m in module_locators}

    @qik.func.cached_property
    def modules_by_path(self) -> dict[str, ModuleLocator]:
        return {m.path: m for m in self.modules_by_name.values()}


class ConfCommands(Base, frozen=True):
    deps: list[str | Dep] = []


class ConfPydist(Base, frozen=True):
    versions: dict[str, str] = {}
    modules: dict[str, str] = {}
    ignore_missing: bool = False
    ignore_missing_modules: bool = False


class Conf(Base, frozen=True):
    commands: ConfCommands = msgspec.field(default_factory=ConfCommands)
    pydist: ConfPydist = msgspec.field(default_factory=ConfPydist)
    plugins: dict[str, Any] = {}


class PluginsMixin:
    """Parses the root qik.toml file for plugins.

    Allows us to dynamically determine the structure of the config based on installed
    plugins.
    """

    plugins: list[str | PluginLocator] = []

    @qik.func.cached_property
    def plugins_by_name(self) -> dict[str, PluginLocator]:
        plugin_locators = (
            PluginLocator(name=p.split(".", 1)[-1], pyimport=p) if isinstance(p, str) else p
            for p in self.plugins
        )
        return {p.name: p for p in plugin_locators}

    @qik.func.cached_property
    def plugins_by_pyimport(self) -> dict[str, PluginLocator]:
        return {p.pyimport: p for p in self.plugins_by_name.values()}


class Plugins(msgspec.Struct, PluginsMixin, frozen=True):
    """Parses the root qik.toml file for plugins.

    Allows us to dynamically determine the structure of the config based on installed
    plugins.
    """

    plugins: list[str | PluginLocator] = []


class Project(ModuleOrPlugin, PluginsMixin, frozen=True):
    plugins: list[str | PluginLocator] = []
    plugin_cache: str | qik.unset.UnsetType = qik.unset.UNSET
    ctx: list[str | Var] = []
    caches: dict[str, Cache] = {}
    spaces: dict[str, Space] = {}
    conf: Conf = msgspec.field(default_factory=Conf)

    @qik.func.cached_property
    def ctx_vars(self) -> dict[str, Var]:
        return dict((v, Var(v)) if isinstance(v, str) else (v.name, v) for v in self.ctx)

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


def _load_plugins(conf: Plugins) -> None:
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
                ) from e
            else:
                # TODO: Show that this is an unexpected error. Currently CLI
                # users get a raw stack trace.
                raise


def _parse_project_config(contents: bytes, plugins_conf: Plugins) -> Project:
    """Dynamically generate a Project config class based on installed plugins."""

    dep_plugin_types = _PLUGIN_TYPES["dep"]
    cache_plugin_types = _PLUGIN_TYPES["cache"]
    venv_plugin_types = _PLUGIN_TYPES["venv"]

    DynamicCacheTypes = Union[(Cache, *(cls for cls, _ in cache_plugin_types.values()))]
    DynamicVenvTypes = Union[(Venv, *(cls for cls, _ in venv_plugin_types.values()))]
    DynamicDeps = Union[
        (
            str,
            GlobDep,
            CmdDep,
            PydistDep,
            ConstDep,
            LoadDep,
            *(cls for cls, _ in dep_plugin_types.values()),
        )
    ]

    DynamicSpace = msgspec.defstruct(
        "DynamicSpace",
        [("venv", DynamicVenvTypes | str | None, None)],  # type: ignore
        bases=(Space,),
        frozen=True,
    )
    DynamicCmd = msgspec.defstruct(
        "DynamicCmd", [("deps", list[DynamicDeps], [])], bases=(Cmd,), frozen=True
    )

    DynamicConfCommands = msgspec.defstruct(
        "DynamicConfCommands",
        [("deps", list[DynamicDeps], [])],
        bases=(ConfCommands,),
        frozen=True,
    )
    DynamicConfPlugins = msgspec.defstruct(
        "DynamicConfPlugins",
        [
            (
                plugins_conf.plugins_by_pyimport[plugin_pyimport].name,
                plugin_conf,
                msgspec.field(default_factory=plugin_conf),
            )
            for plugin_pyimport, plugin_conf in _CONF_TYPES.items()
        ],
        bases=(Base,),
        frozen=True,
    )

    DynamicConf = msgspec.defstruct(
        "DynamicConf",
        [
            ("commands", DynamicConfCommands, msgspec.field(default_factory=DynamicConfCommands)),
            ("plugins", DynamicConfPlugins, msgspec.field(default_factory=DynamicConfPlugins)),
        ],
        bases=(Conf,),
        frozen=True,
    )

    # Must register as part of the global namespace in order for msgspec to
    # recognize dynamic nested type.
    globals()["DynamicSpace"] = DynamicSpace
    globals()["DynamicCmd"] = DynamicCmd
    globals()["DynamicCacheTypes"] = DynamicCacheTypes
    globals()["DynamicDeps"] = DynamicDeps
    globals()["DynamicConfCommands"] = DynamicConfCommands
    globals()["DynamicConf"] = DynamicConf

    DynamicProject = msgspec.defstruct(
        "DynamicProject",
        [
            ("venvs", dict[str, DynamicVenvTypes], {}),
            ("caches", dict[str, DynamicCacheTypes], {}),
            ("spaces", dict[str, DynamicSpace], {}),
            ("commands", dict[str, DynamicCmd], {}),
            ("conf", DynamicConf, msgspec.field(default_factory=DynamicConf)),
        ],
        bases=(Project,),
        frozen=True,
    )

    return msgspec.toml.decode(contents, type=DynamicProject)  # type: ignore


@qik.func.cache
def _project() -> tuple[Project, pathlib.Path]:
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
        plugins_conf = msgspec.toml.decode(contents, type=Plugins)
        _load_plugins(plugins_conf)
        return _parse_project_config(contents, plugins_conf), qik_toml
    else:
        raise qik.errors.ConfigNotFound("Could not locate qik.toml configuration file.")


@qik.func.cache
def project() -> Project:
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
    if "/" in uri:
        return tuple(uri.rsplit("/", 1))  # type: ignore
    elif "." in uri:
        return tuple(uri.rsplit(".", 1))  # type: ignore
    else:
        return (None, uri)


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
