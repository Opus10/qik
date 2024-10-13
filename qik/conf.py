"""Qik project and configuration loading."""

from __future__ import annotations

import collections
import importlib.util
import os.path
import pathlib
import sys
from types import UnionType
from typing import Any, ClassVar, Generator, Literal, TypeAlias, TypeVar, Union

import msgspec.structs
import msgspec.toml

import qik.conf
import qik.errors
import qik.func
import qik.unset

CtxNamespace: TypeAlias = Literal["qik", "project", "modules", "plugins"]
SerializableVarType: TypeAlias = str | bool | int
VarType: TypeAlias = SerializableVarType | list[str]
VAR_T = TypeVar("VAR_T", str, bool, int, list[str], None)
CacheWhen: TypeAlias = Literal["success", "failed", "finished"]
CacheStatus: TypeAlias = Literal["warm", "code"]


# Dynamic objects registered by plugins
_PLUGIN_TYPES: dict[str, dict[str, tuple[type[BasePluggable], str]]] = collections.defaultdict(
    dict
)
# Dynamic conf classes registered by plugins
_CONF_TYPES: dict[str, type[msgspec.Struct]] = {}
# Default venv type
_VENV_TYPE: type[Venv] | None = None


def register_type(plugin_type: type[BasePluggable], factory: str) -> None:
    if plugin_type.plugin_type_name == "venv":
        global _VENV_TYPE
        _VENV_TYPE = plugin_type  # type: ignore

    _PLUGIN_TYPES[plugin_type.plugin_type_name][str(plugin_type.__struct_config__.tag)] = (
        plugin_type,
        factory,
    )


def register_conf(conf_type: type[qik.conf.PluginConf]) -> None:
    _CONF_TYPES[str(conf_type.__struct_config__.tag)] = conf_type


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
    default: SerializableVarType | qik.unset.UnsetType = qik.unset.UNSET
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
    commands: dict[str, Cmd | str] = {}


class BaseLocator(Base, frozen=True):
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
    name: str
    path: str

    @qik.func.cached_property
    def pyimport(self) -> str:
        return pyimport(self.path)

    @qik.func.cached_property
    def dir(self) -> pathlib.Path:
        # TODO: While this handles most windows paths, it does not handle literal '/'
        # in paths that are escaped (e.g. my\/file/path)
        return pathlib.Path(self.path.replace("/", os.path.sep))


class BasePluginLocator(BaseLocator, frozen=True):
    @qik.func.cached_property
    def dir(self) -> pathlib.Path:
        spec = importlib.util.find_spec(self.pyimport)
        if not spec or not spec.origin:
            raise qik.errors.PluginImport(f'Could not import plugin "{self.pyimport}"')

        return pathlib.Path(spec.origin).parent


# Note - we use forbid_unknown_fields=False because this is used in our first pass
# to load just the plugins from the conf file.
class PluginLocator(BasePluginLocator, frozen=True, forbid_unknown_fields=False):
    pyimport: str  # type: ignore


class PluginConf(BasePluginLocator, frozen=True, tag_field="pyimport"):
    @property
    def pyimport(self) -> str:  # type: ignore
        return str(self.__struct_config__.tag)


class Venv(BasePluggable, frozen=True, tag_field="type", kw_only=True):
    plugin_type_name: ClassVar[str] = "venv"
    install_cmd: ClassVar[str | None] = None
    reqs: str | list[str]
    lock: str | None = None


class SpaceVenv(Venv, frozen=True, tag="space", kw_only=True):
    name: str
    reqs: str | list[str] = []


class ActiveVenv(Venv, frozen=True, tag="active"):
    reqs: str | list[str] = []


class Cache(BasePluggable, frozen=True, tag_field="type"):
    plugin_type_name: ClassVar[str] = "cache"


class SpaceLocator(Base, tag_field="type", frozen=True, tag="space"):
    name: str


class Space(Base, frozen=True):
    root: str | None = None
    modules: list[str | ModuleLocator] = []
    fence: list[str | SpaceLocator] | bool = []
    venv: Venv | str | list[str] | None = None
    dotenv: str | list[str] | None = None

    @qik.func.cached_property
    def modules_by_name(self) -> dict[str, ModuleLocator]:
        module_locators = (
            ModuleLocator(name=m, path=m) if isinstance(m, str) else m for m in self.modules
        )
        return {m.name: m for m in module_locators}

    @qik.func.cached_property
    def modules_by_path(self) -> dict[str, ModuleLocator]:
        return {m.path: m for m in self.modules_by_name.values()}


class Pydist(Base, frozen=True):
    versions: dict[str, str] = {}
    ignore_missing: bool = False
    ignore_missing_modules: bool = False
    modules: dict[str, str] = {}


class PluginsMixin:
    """Parses the root qik.toml file for plugins.

    Allows us to dynamically determine the structure of the config based on installed
    plugins.
    """

    plugins: dict[str, str | PluginLocator] = {}

    @qik.func.cached_property
    def plugins_by_name(self) -> dict[str, PluginLocator]:
        return {
            name: PluginLocator(pyimport=p) if isinstance(p, str) else p
            for name, p in self.plugins.items()
        }

    @qik.func.cached_property
    def plugins_by_pyimport(self) -> dict[str, tuple[str, PluginLocator]]:
        return {p.pyimport: (name, p) for name, p in self.plugins_by_name.items()}


class Plugins(msgspec.Struct, PluginsMixin, frozen=True, forbid_unknown_fields=False):
    """Parses the root qik.toml file for plugins.

    Allows us to dynamically determine the structure of the config based on installed
    plugins.
    """

    plugins: dict[str, str | PluginLocator] = {}


class BaseConf(Base, frozen=True):
    deps: list[str | Dep] = []


class Defaults(Base, frozen=True):
    cache: str | qik.unset.UnsetType = qik.unset.UNSET
    cache_when: CacheWhen | qik.unset.UnsetType = qik.unset.UNSET
    python_path: str = "."
    # Note: "None" is the sentinel value for these. We can't mix UNSET with a list.
    venv: Venv | str | list[str] | None = None
    dotenv: str | list[str] | None = None


class Project(ModuleOrPlugin, PluginsMixin, frozen=True):
    plugins: dict[str, str | PluginLocator] = {}
    ctx: list[str | Var] = []
    caches: dict[str, Cache] = {}
    spaces: dict[str, Space | str | list[str]] = {}
    base: BaseConf = msgspec.field(default_factory=BaseConf)
    defaults: Defaults = msgspec.field(default_factory=Defaults)
    pydist: Pydist = msgspec.field(default_factory=Pydist)

    @qik.func.cached_property
    def resolved_spaces(self) -> dict[str, Space]:
        return {
            name: Space(venv=space) if isinstance(space, str | list) else space
            for name, space in self.spaces.items()
        }

    @qik.func.cached_property
    def ctx_vars(self) -> dict[str, Var]:
        return dict((v, Var(v)) if isinstance(v, str) else (v.name, v) for v in self.ctx)

    @qik.func.cached_property
    def modules_by_name(self) -> dict[str, ModuleLocator]:
        return {
            name: locator
            for space in self.resolved_spaces.values()
            for name, locator in space.modules_by_name.items()
        }

    @qik.func.cached_property
    def modules_by_path(self) -> dict[str, ModuleLocator]:
        return {m.path: m for m in self.modules_by_name.values()}


def _load_plugins(conf: Plugins) -> None:
    """Load plugins and return the Project configuration."""
    for plugin in conf.plugins.values():
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


class BaseDynamicPlugins(Base, frozen=True):
    def items(self) -> Generator[tuple[str, Any]]:  # type: ignore
        for key in self.__struct_fields__:
            yield (key, getattr(self, key))


def _parse_project_config(contents: bytes, plugins_conf: Plugins) -> Project:
    """Dynamically generate a Project config class based on installed plugins."""

    dep_plugin_types = _PLUGIN_TYPES["dep"]
    cache_plugin_types = _PLUGIN_TYPES["cache"]
    venv_plugin_types = _PLUGIN_TYPES["venv"]

    DynamicCacheTypes = Union[(Cache, *(cls for cls, _ in cache_plugin_types.values()))]
    DynamicVenvTypes = Union[
        (ActiveVenv, SpaceVenv, *(cls for cls, _ in venv_plugin_types.values()))
    ]
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
    DynamicBaseConf = msgspec.defstruct(
        "DynamicBaseConf",
        [("deps", list[DynamicDeps], [])],  # type: ignore
        bases=(BaseConf,),
        frozen=True,
    )

    DynamicSpace = msgspec.defstruct(
        "DynamicSpace",
        [("venv", DynamicVenvTypes | str | list[str] | None, None)],  # type: ignore
        bases=(Space,),
        frozen=True,
    )
    DynamicCmd = msgspec.defstruct(
        "DynamicCmd", [("deps", list[DynamicDeps], [])], bases=(Cmd,), frozen=True
    )

    existing_plugin_confs = {
        pyimport: PluginLocator for pyimport in plugins_conf.plugins_by_pyimport
    }
    DynamicPlugins = msgspec.defstruct(
        "DynamicPlugins",
        [
            (
                plugins_conf.plugins_by_pyimport[plugin_pyimport][0],
                plugin_conf | str,  # type: ignore
            )
            for plugin_pyimport, plugin_conf in (existing_plugin_confs | _CONF_TYPES).items()
        ],
        bases=(BaseDynamicPlugins,),
        frozen=True,
    )

    DynamicDefaults = msgspec.defstruct(
        "DynamicDefaults",
        [("venv", DynamicVenvTypes | str | list[str] | None, None)],  # type: ignore
        bases=(Defaults,),
        frozen=True,
    )

    # Must register as part of the global namespace in order for msgspec to
    # recognize dynamic nested type.
    globals()["DynamicSpace"] = DynamicSpace
    globals()["DynamicCmd"] = DynamicCmd
    globals()["DynamicCacheTypes"] = DynamicCacheTypes
    globals()["DynamicDeps"] = DynamicDeps
    globals()["DynamicBaseConf"] = DynamicBaseConf
    globals()["DynamicPlugins"] = DynamicPlugins
    globals()["DynamicDefaults"] = DynamicDefaults

    DynamicProject = msgspec.defstruct(
        "DynamicProject",
        [
            ("venvs", dict[str, DynamicVenvTypes], {}),
            ("caches", dict[str, DynamicCacheTypes], {}),
            ("spaces", dict[str, DynamicSpace | str | list[str]], {}),
            ("commands", dict[str, DynamicCmd | str], {}),
            ("base", DynamicBaseConf, msgspec.field(default_factory=DynamicBaseConf)),
            ("defaults", DynamicDefaults, msgspec.field(default_factory=DynamicDefaults)),
            ("plugins", DynamicPlugins, msgspec.field(default_factory=DynamicPlugins)),
        ],
        bases=(Project,),
        frozen=True,
    )

    return msgspec.toml.decode(contents, type=DynamicProject)  # type: ignore


@qik.func.cache
def load() -> tuple[Project, pathlib.Path]:
    """Load the project configuration and file.

    This serves as an entry point for all of qik, so we set the python path
    here too.
    """
    cwd = pathlib.Path.cwd()
    qik_toml: pathlib.Path | None = None

    for directory in (cwd, *cwd.parents):
        if (directory / "qik.toml").is_file():
            qik_toml = directory / "qik.toml"

        if (directory / ".git").is_dir():
            break

    if qik_toml:
        try:
            contents = qik_toml.read_bytes()
            plugins_conf = msgspec.toml.decode(contents, type=Plugins)
            _load_plugins(plugins_conf)
            conf = _parse_project_config(contents, plugins_conf)
        except msgspec.ValidationError as e:
            raise qik.errors.ConfigParse(f"Error parsing qik.toml: {e}") from e

        python_path = qik_toml.parent / conf.defaults.python_path
        sys.path.insert(0, str(python_path))
        return conf, qik_toml
    else:
        raise qik.errors.ConfigNotFound("Could not locate qik.toml configuration file.")


@qik.func.cache
def project() -> Project:
    return load()[0]


@qik.func.cache
def module_locator(uri: str, *, by_path: bool = False) -> ModuleLocator:
    """Get module locator."""
    proj = project()
    lookup = proj.modules_by_path if by_path else proj.modules_by_name
    if uri not in lookup:
        raise qik.errors.ModuleNotFound(f'Module "{uri}" not configured in {location().name}.')

    return lookup[uri]


@qik.func.cache
def plugin_locator(uri: str, *, by_pyimport: bool = False) -> tuple[str, PluginLocator]:
    """Get plugin locator."""
    proj = project()
    lookup = proj.plugins_by_pyimport if by_pyimport else proj.plugins_by_name
    if uri not in lookup:
        raise qik.errors.PluginNotFound(f'Plugin "{uri}" not configured in {location().name}.')

    if by_pyimport:
        return proj.plugins_by_pyimport[uri]
    else:
        return uri, proj.plugins_by_name[uri]


@qik.func.cache
def plugin(pyimport: str) -> PluginConf:
    """Get dynamic plugin configuration."""
    proj = project()
    conf = getattr(proj.plugins, proj.plugins_by_pyimport[pyimport][0])
    if isinstance(conf, str):
        return _CONF_TYPES[pyimport]()  # type: ignore
    else:
        return conf  # type: ignore


@qik.func.cache
def search(name: str | None = None) -> ModuleOrPlugin:
    """Search configuration for a given module, plugin, or project."""
    if not name:
        return project()
    else:
        try:
            return module_locator(name).conf
        except qik.errors.ModuleNotFound:
            try:
                return plugin_locator(name)[1].conf
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
    conf = search(module)
    if name not in conf.commands:
        raise qik.errors.CommandNotFound(f'Command "{uri}" not configured.')

    cmd_conf = conf.commands[name]
    return Cmd(exec=cmd_conf) if isinstance(cmd_conf, str) else cmd_conf


@qik.func.cache
def root() -> pathlib.Path:
    """Get the absolute root project directory."""
    return load()[1].parent


@qik.func.cache
def abs_python_path() -> pathlib.Path:
    """Get the absolute python path."""
    return load()[1].parent / project().defaults.python_path


@qik.func.cache
def priv_work_dir(rel: bool = False) -> pathlib.Path:
    """Get the private work directory."""
    return root() / "._qik" if not rel else pathlib.Path("._qik")


@qik.func.cache
def pub_work_dir(rel: bool = False) -> pathlib.Path:
    """Get the public work directory."""
    return root() / ".qik" if not rel else pathlib.Path(".qik")


@qik.func.cache
def location() -> pathlib.Path:
    """Get the root configuration file."""
    return load()[1]


@qik.func.cache
def pyimport(path: str) -> str:
    """Return the python import for a path."""
    python_path = project().defaults.python_path
    if python_path == ".":
        return path.replace("/", ".")
    else:
        return str(pathlib.Path(path).relative_to(python_path)).replace("/", ".")


def default_venv_type() -> type[Venv]:
    """Get the default venv type."""
    load()
    return _VENV_TYPE or ActiveVenv
