"""Manage global run context."""

from __future__ import annotations

import contextlib
import contextvars
import functools
import os
import threading
from typing import TYPE_CHECKING, Any, Iterator, Literal, TypeVar, overload

import msgspec
import psutil

import qik.arch
import qik.conf
import qik.unset

if TYPE_CHECKING:
    from qik.runnable import Runnable
    from qik.runner import Runner


_RUNNER: Runner | None = None
_PROFILE: str = "default"
_RUNNABLE: contextvars.ContextVar[Runnable | None] = contextvars.ContextVar(
    "_RUNNABLE", default=None
)
_CURR_WORKER_ID: int = 0
_WORKER_IDS: dict[str, int] = {}
_WORKER_LOCK = threading.Lock()
_WORKER_ID: contextvars.ContextVar[int | None] = contextvars.ContextVar("_WORKER_ID", default=None)


def profile() -> str:
    """Get which profile we're using."""
    return _PROFILE


@contextlib.contextmanager
def set_profile(name: str) -> Iterator[None]:
    """Set which profile we're using."""
    global _PROFILE
    old_profile = _PROFILE
    _PROFILE = name

    try:
        yield
    finally:
        _PROFILE = old_profile


def runner() -> Runner:
    """Get the current runner."""
    if not _RUNNER:
        raise RuntimeError("No runner set in context.")

    return _RUNNER


@contextlib.contextmanager
def set_runner(runner: Runner) -> Iterator[None]:
    """Set the current runner."""
    global _RUNNER
    old_runner = _RUNNER
    _RUNNER = runner

    try:
        yield
    finally:
        _RUNNER = old_runner


def runnable() -> Runnable:
    """Get the current runnable."""
    if runnable := _RUNNABLE.get():
        return runnable
    else:
        raise RuntimeError("No runnable set in context.")


@contextlib.contextmanager
def set_runnable(runnable: Runnable) -> Iterator[None]:
    """Set the current runnable."""
    old_runnable = _RUNNABLE.set(runnable)
    try:
        yield
    finally:
        _RUNNABLE.reset(old_runnable)


def worker_id() -> int:
    """Get the current worker ID."""
    if worker_id := _WORKER_ID.get():
        return worker_id
    else:
        raise RuntimeError("No worker ID set in context.")


@contextlib.contextmanager
def set_worker_id() -> Iterator[None]:
    """Set the current worker ID."""
    global _CURR_WORKER_ID, _WORKER_IDS
    thread_ident = threading.get_ident()

    if not _WORKER_IDS.get(thread_ident):
        with _WORKER_LOCK:
            _CURR_WORKER_ID += 1
            _WORKER_IDS[thread_ident] = _CURR_WORKER_ID

    old_worker_id = _WORKER_ID.set(_WORKER_IDS[thread_ident])
    try:
        yield
    finally:
        _WORKER_ID.reset(old_worker_id)


class QikCtx(msgspec.Struct, forbid_unknown_fields=True, rename="kebab", dict=True):
    # Runtime behavior
    isolated: bool = False
    watch: bool = False
    cache: str | None = None
    force: bool = False
    ls: bool = False
    workers: int = msgspec.field(default_factory=lambda: psutil.cpu_count(logical=True))
    fail: bool = False
    cache_when: qik.conf.CacheWhen = "success"
    verbosity: int = 1

    # Selectors
    since: str | None = None
    commands: list[str] = []
    modules: list[str] = []
    cache_status: qik.conf.CacheStatus | None = None
    cache_types: list[str] = []

    @functools.cached_property
    def arch(self) -> qik.arch.ArchType:
        return qik.arch.get()


@functools.cache
def _var_struct(
    namespace: qik.conf.CtxNamespace, module_name: str | None = None
) -> type[msgspec.Struct]:
    """Get a struct of vars for a module."""
    if namespace == "qik":
        return QikCtx
    else:
        conf = qik.conf.get(module_name)
        return msgspec.defstruct(
            "VarStruct",
            [(v.name, v.py_type, v.default) for v in conf.vars_dict.values()],
            forbid_unknown_fields=True,
            rename="kebab",
        )


@overload
def module(namespace: Literal["qik"], /) -> QikCtx: ...


@overload
def module(namespace: qik.conf.CtxNamespace, name: str | None = ..., /) -> msgspec.Struct: ...


def module(
    namespace: qik.conf.CtxNamespace, name: str | None = None, /
) -> QikCtx | msgspec.Struct:
    return _module(namespace, name, profile=_PROFILE)


@functools.cache
def _module(
    namespace: qik.conf.CtxNamespace, name: str | None = None, /, profile: str = "default"
) -> QikCtx | msgspec.Struct:
    """Get context for a module."""
    module_name = name
    proj = qik.conf.project()
    module_prefix = "" if not module_name else f"{module_name}."
    env_prefix = f"{namespace}__" if not module_name else f"{namespace}__{module_name}__"
    var_struct = _var_struct(namespace, module_name)

    proj_ctx = {"default": {}, "ci": {}} | proj.ctx
    if profile not in proj_ctx:
        raise ValueError(f'Context profile "{profile}" is not configured.')

    ctx = proj_ctx[profile].get(namespace, {})
    if name is None:
        ctx = {k: v for k, v in ctx.items() if not isinstance(v, dict)}
    else:
        parts = module_name.split(".")
        for part in parts:
            if isinstance(ctx.get(part), dict):
                ctx: dict[str, Any] = ctx[part]
            else:
                break

    parsed = msgspec.convert(ctx, type=var_struct)

    def _get_val(var_name: str, type_val: str | type) -> qik.conf.VarType | qik.unset.UnsetType:
        str_type = type_val.__name__ if isinstance(type_val, type) else str(type_val)
        env_key = f"{env_prefix}{var_name}".upper()
        env_setting = os.environ.get(env_key)
        if env_setting is None:
            return getattr(parsed, var_name)

        match str_type:
            case "str" | "str | None":
                return env_setting
            case "int" | "int | None":
                try:
                    return int(env_setting)
                except ValueError as exc:
                    raise ValueError(
                        f'Unable to cast env ctx {env_key} value "{env_setting}" as int'
                    ) from exc
            case "bool" | "bool | None":
                if env_setting.lower().strip() in ("yes", "true", "1", "no", "false", "0"):
                    return env_setting.lower().strip() in ["yes", "true", "1"]
                else:
                    raise ValueError(
                        f'Unable to cast env ctx {env_key} value "{env_setting}" as bool.'
                    )
            case other:
                raise AssertionError(f"Unexpected ctx var type: {other}")

    for var_name, var_type in var_struct.__annotations__.items():
        setattr(parsed, var_name, _get_val(var_name, var_type))
        if getattr(parsed, var_name) is qik.unset.UNSET:
            raise ValueError(f'No value supplied for "{namespace}.{module_prefix}{var_name}" ctx.')

    return parsed


@contextlib.contextmanager
def set_vars(
    namespace: qik.conf.CtxNamespace,
    module_name: str | None = None,
    **vars: qik.conf.VarType | qik.unset.UnsetType,
) -> Iterator[None]:
    curr_vars = module(namespace, module_name)
    old_vars = msgspec.structs.replace(curr_vars)
    for name, val in vars.items():
        if val is not qik.unset.UNSET:
            setattr(curr_vars, name, val)

    try:
        yield
    finally:
        for name in old_vars.__struct_fields__:
            setattr(curr_vars, name, getattr(old_vars, name))


class _ModuleCtx:
    """A utility class for accessing module context as an object."""

    def __init__(self, namespace: str, module_name: str | None):
        self._namespace = namespace
        self._module_name = module_name

    @functools.cached_property
    def _prefix(self) -> str:
        mod_name = f".{self._module_name}" if self._module_name else ""
        return f"{self._namespace}{mod_name}"

    @functools.cached_property
    def _module_ctx(self) -> msgspec.Struct | QikCtx:
        return module(self._namespace, self._module_name)

    def __getattr__(self, key: str) -> qik.conf.VarType:
        try:
            return getattr(self._module_ctx, key)
        except AttributeError as exc:
            raise KeyError(f'Ctx "{self._prefix}.{key}" not configured') from exc


class _ModulesCtx:
    """A utility class for accessing modules/plugins context as an object."""

    def __init__(self, namespace: str):
        self._namespace = namespace
        self._cache: dict[str, _ModuleCtx] = {}

    def __getattr__(self, module_name: str) -> _ModuleCtx:
        if module_name not in self._cache:
            self._cache[module_name] = _ModuleCtx(self._namespace, module_name)

        return self._cache[module_name]


class Ctx:
    """A singleton class for accessing context as an object."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __getattribute__(self, name: str) -> Any:
        try:
            return super().__getattribute__(name)
        except AttributeError as exc:
            raise KeyError(
                f'Ctx namespace "{name}" is invalid. Use project, qik, modules, or plugings.'
            ) from exc

    @functools.cached_property
    def project(self) -> _ModuleCtx:
        return _ModuleCtx("project", None)

    @functools.cached_property
    def qik(self) -> _ModuleCtx:
        return _ModuleCtx("qik", None)

    @functools.cached_property
    def modules(self) -> _ModuleCtx:
        return _ModulesCtx("modules")

    @functools.cached_property
    def plugins(self) -> _ModuleCtx:
        return _ModuleCtx("plugins")


_CTX = Ctx()
FMT_STR_T = TypeVar("FMT_STR_T", str, qik.unset.UnsetType, None)


def format(val: FMT_STR_T, module: qik.conf.ModulePath | None = None) -> FMT_STR_T:
    """Formats a string with context and other variables"""
    return val.format(module=module, ctx=_CTX) if isinstance(val, str) else val
