"""Manage global run context."""

from __future__ import annotations

import contextlib
import contextvars
import os
import threading
from typing import TYPE_CHECKING, Any, Iterator, TypeVar, overload

import msgspec

import qik.arch
import qik.conf
import qik.errors
import qik.func as qik_func
import qik.unset

if TYPE_CHECKING:
    from qik.runnable import Runnable
    from qik.runner import Runner


_RUNNER: Runner | None = None
_RUNNABLE: contextvars.ContextVar[Runnable | None] = contextvars.ContextVar(
    "_RUNNABLE", default=None
)
_CURR_WORKER_ID: int = 0
_WORKER_IDS: dict[int, int] = {}
_WORKER_LOCK = threading.Lock()
_WORKER_ID: contextvars.ContextVar[int | None] = contextvars.ContextVar("_WORKER_ID", default=None)


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
    force: bool = False
    ls: bool = False
    workers: int = msgspec.field(default_factory=lambda: os.cpu_count() or 1)
    fail: bool = False
    verbosity: int = 1

    # Selectors
    since: str | None = None
    commands: list[str] = []
    modules: list[str] = []
    spaces: list[str] = []
    cache_status: qik.conf.CacheStatus | None = None
    caches: list[str] = []

    @qik_func.cached_property
    def arch(self) -> qik.arch.ArchType:
        return qik.arch.get()


@qik_func.cache
def _var_struct(namespace: qik.conf.CtxNamespace | None = None) -> type[msgspec.Struct]:
    """Get a struct of vars for a module."""
    if namespace == "qik":
        return QikCtx
    else:
        proj = qik.conf.project()
        return msgspec.defstruct(
            "VarStruct",
            [(v.name, v.pytype, v.default) for v in proj.ctx_vars.values()],  # type: ignore
            forbid_unknown_fields=True,
            rename="kebab",
        )


@overload
def by_namespace(name: qik.conf.CtxNamespace, /) -> QikCtx: ...


@overload
def by_namespace(name: None, /) -> msgspec.Struct: ...


def by_namespace(name: qik.conf.CtxNamespace | None, /) -> QikCtx | msgspec.Struct:
    return _by_namespace(name)


@qik_func.cache
def _by_namespace(name: qik.conf.CtxNamespace | None) -> QikCtx | msgspec.Struct:
    """Get context for a namesapce."""
    env_prefix = f"{name}__" if name else ""
    namespace_prefix = f"{name}." if name else ""
    var_struct = _var_struct(name)
    parsed = msgspec.convert({}, type=var_struct)

    def _get_val(var_name: str, type_val: str | type) -> qik.conf.VarType | qik.unset.UnsetType:
        str_type = type_val.__name__ if isinstance(type_val, type) else str(type_val)
        env_key = f"{env_prefix}{var_name}".upper()
        env_setting = os.environ.get(env_key)
        if env_setting is None:
            return getattr(parsed, var_name)

        match str_type:
            case "str" | "str | None" | "qik.conf.CacheStatus | None":
                return env_setting
            case "int" | "int | None":
                try:
                    return int(env_setting)
                except ValueError as exc:
                    raise qik.errors.EnvCast(
                        f'Unable to cast env ctx {env_key} value "{env_setting}" as int'
                    ) from exc
            case "bool" | "bool | None":
                if env_setting.lower().strip() in ("yes", "true", "1", "no", "false", "0"):
                    return env_setting.lower().strip() in ["yes", "true", "1"]
                else:
                    raise qik.errors.EnvCast(
                        f'Unable to cast env ctx {env_key} value "{env_setting}" as bool.'
                    )
            case "list[str]":
                return env_setting.split(",")
            case other:
                raise AssertionError(f"Unexpected ctx var type: {other}")

    for var_name, var_type in var_struct.__annotations__.items():
        setattr(parsed, var_name, _get_val(var_name, var_type))
        if isinstance(getattr(parsed, var_name), qik.unset.UnsetType):
            raise qik.errors.CtxValueNotFound(
                f'No value supplied for "{namespace_prefix}{var_name}" ctx.'
            )

    return parsed


@contextlib.contextmanager
def set_vars(
    namespace: qik.conf.CtxNamespace,
    **vars: qik.conf.VarType | qik.unset.UnsetType,
) -> Iterator[None]:
    curr_vars = by_namespace(namespace)
    old_vars = msgspec.structs.replace(curr_vars)
    for name, val in vars.items():
        if not isinstance(val, qik.unset.UnsetType):
            setattr(curr_vars, name, val)

    try:
        yield
    finally:
        for name in old_vars.__struct_fields__:
            setattr(curr_vars, name, getattr(old_vars, name))


class _NamespaceCtx:
    """A utility class for accessing namespaced context as an object."""

    def __init__(self, namespace: qik.conf.CtxNamespace | None):
        self._namespace: qik.conf.CtxNamespace | None = namespace
        self._prefix = f"{namespace}." if namespace else ""

    @qik_func.cached_property
    def _namespace_ctx(self) -> msgspec.Struct | QikCtx:
        return by_namespace(self._namespace)

    def __getattr__(self, key: str) -> qik.conf.VarType:
        try:
            return getattr(self._namespace_ctx, key)
        except AttributeError as exc:
            raise qik.errors.UnconfiguredCtx(f'Ctx "{self._prefix}{key}" not configured') from exc


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
        except AttributeError:
            return getattr(self.project, name)

    @qik_func.cached_property
    def project(self) -> _NamespaceCtx:
        return _NamespaceCtx(None)

    @qik_func.cached_property
    def qik(self) -> _NamespaceCtx:
        return _NamespaceCtx("qik")


_CTX = Ctx()
FMT_STR_T = TypeVar("FMT_STR_T", bound=str | qik.unset.UnsetType | None)


def format(val: FMT_STR_T, module: qik.conf.ModuleLocator | None = None) -> FMT_STR_T:
    """Formats a string with context and other variables"""
    return val.format(module=module, ctx=_CTX) if isinstance(val, str) else val
