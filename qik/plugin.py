from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import qik.conf

_CACHE_REGISTRY: dict[str, type[qik.conf.Cache]] = {}


def register_cache(name: str, cache: type[qik.conf.Cache]) -> None:
    _CACHE_REGISTRY[name] = cache

