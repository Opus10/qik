from __future__ import annotations

import qik.conf
import qik.ctx
import qik.func
import qik.unset


class PygraphDepConf(qik.conf.Dep, tag="pygraph", frozen=True):
    pyimport: str


class PygraphPluginConf(qik.conf.PluginConf, frozen=True, dict=True, tag="qik.pygraph"):
    ignore_type_checking: bool = False
    ignore_pydists: bool = False
    cache: str | qik.unset.UnsetType = qik.unset.UNSET
    build_cache: str | qik.unset.UnsetType = qik.unset.UNSET
    lock_cache: str | qik.unset.UnsetType = qik.unset.UNSET
    check_cache: str | qik.unset.UnsetType = qik.unset.UNSET

    @qik.func.cached_property
    def resolved_build_cache(self) -> str:
        return qik.ctx.format(
            qik.unset.coalesce(
                self.build_cache,
                self.cache,
                qik.conf.project().defaults.cache,
                default="local",
            )
        )

    @qik.func.cached_property
    def resolved_lock_cache(self) -> str:
        return qik.ctx.format(
            qik.unset.coalesce(
                self.lock_cache,
                self.cache,
                qik.conf.project().defaults.cache,
                default="local",
            )
        )

    @qik.func.cached_property
    def resolved_check_cache(self) -> str:
        return qik.ctx.format(
            qik.unset.coalesce(
                self.check_cache,
                self.cache,
                qik.conf.project().defaults.cache,
                default="local",
            )
        )


qik.conf.register_type(PygraphDepConf, "qik.pygraph.dep.factory")
qik.conf.register_conf(PygraphPluginConf)
