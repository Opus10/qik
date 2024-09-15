from typing import Any, TypeAlias, TypeGuard, TypeVar

T = TypeVar("T")
UnsetType: TypeAlias = frozenset

UNSET = frozenset([None])


def is_unset(val: Any) -> TypeGuard[UnsetType]:
    return val is UNSET


def is_not_unset(val: T | UnsetType) -> TypeGuard[T]:
    return not is_unset(val)
