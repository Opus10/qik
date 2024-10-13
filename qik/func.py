"""Custom caching decorators similar to functools."""

from __future__ import annotations

import functools
from typing import Callable, Final, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


_RUN_CACHED_FUNCS: Final[list[Callable]] = []
_RUN_CACHED_PROPS: Final[list[tuple[dict, str]]] = []


cache = functools.cache
lru_cache = functools.lru_cache
cached_property = functools.cached_property


def per_run_cache(func: Callable[P, T]) -> Callable[P, T]:
    """Cache a function's results for the duration of a run."""

    cached_func = cache(func)
    _RUN_CACHED_FUNCS.append(cached_func)
    return cached_func  # type: ignore


_NOT_FOUND = object()


class per_run_cached_property(functools.cached_property):
    def __get__(self, instance, owner=None):
        try:
            val = instance.__dict__.get(self.attrname, _NOT_FOUND)
            if val is _NOT_FOUND:
                val = self.func(instance)
                instance.__dict__[self.attrname] = val
                _RUN_CACHED_PROPS.append((instance.__dict__, self.attrname))  # type: ignore

            return val
        except AttributeError:
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {self.attrname!r} property."
            )
            raise TypeError(msg) from None


def clear_per_run_cache() -> None:
    """Clear all run cache."""
    for cache in _RUN_CACHED_FUNCS:
        cache.cache_clear()  # type: ignore

    for dictionary, attr in _RUN_CACHED_PROPS:
        if attr in dictionary:
            del dictionary[attr]
