from __future__ import annotations

import qik.conf
import qik.func
import qik.unset


class PygraphDepConf(qik.conf.Dep, tag="pygraph", frozen=True):
    pyimport: str


class PygraphPluginConf(qik.conf.Base, frozen=True, dict=True):
    ignore_type_checking: bool = False
    ignore_pydists: bool = False
    ignore_missing_module_pydists: bool = False
    module_pydists: dict[str, str] = {}
    cache: str = "repo"
    build_cache: str | qik.unset.UnsetType = qik.unset.UNSET
    lock_cache: str | qik.unset.UnsetType = qik.unset.UNSET

    @qik.func.cached_property
    def resolved_build_cache(self) -> str:
        return self.build_cache if not isinstance(self.build_cache, qik.unset.UnsetType) else self.cache

    @qik.func.cached_property
    def resolved_lock_cache(self) -> str:
        return self.lock_cache if not isinstance(self.lock_cache, qik.unset.UnsetType) else self.cache


qik.conf.register_type(PygraphDepConf, "qik.pygraph.dep.factory")
qik.conf.register_conf(PygraphPluginConf, "qik.pygraph")
