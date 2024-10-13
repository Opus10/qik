from typing import Any, TypeAlias, TypeVar

UnsetType: TypeAlias = frozenset
T = TypeVar("T")

UNSET = frozenset([None])


def coalesce(*args: Any, default: Any) -> Any:
    return next((arg for arg in args if not isinstance(arg, UnsetType | None)), default)
