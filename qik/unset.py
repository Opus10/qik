from types import UnionType
from typing import Any, TypeAlias, TypeVar

UnsetType: TypeAlias = frozenset
T = TypeVar("T")

UNSET = frozenset([None])


def coalesce(*args: Any, default: Any, type: type[T] | UnionType) -> T:
    return next((arg for arg in args if not isinstance(arg, UnsetType)), default)
