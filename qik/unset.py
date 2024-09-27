from typing import TypeAlias, TypeVar

UnsetType: TypeAlias = frozenset
T = TypeVar("T")

UNSET = frozenset([None])


def coalesce(*args: T, default: T | None = None) -> T | None:
    return next((arg for arg in args if not isinstance(arg, UnsetType)), default)
