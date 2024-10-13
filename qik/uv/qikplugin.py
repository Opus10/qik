from typing import ClassVar

import qik.conf
import qik.ctx
import qik.func
import qik.unset


class UVVenvConf(qik.conf.Venv, frozen=True, tag="uv"):
    python: str | qik.unset.UnsetType = qik.unset.UNSET
    constraint: str | qik.conf.SpaceLocator | qik.unset.UnsetType = qik.unset.UNSET
    install_cmd: ClassVar[str] = "uv.install"


class UVPluginConf(qik.conf.PluginConf, frozen=True, dict=True, tag="qik.uv"):
    cache: str | qik.unset.UnsetType = qik.unset.UNSET
    python: str | None = None
    index_url: str | None = None
    extra_index_url: str | None = None
    constraint: str | qik.conf.SpaceLocator | None = None

    @qik.func.cached_property
    def resolved_index_url(self) -> str | None:
        if self.index_url:
            return qik.ctx.format(self.index_url)

    @qik.func.cached_property
    def resolved_extra_index_url(self) -> str | None:
        if self.extra_index_url:
            return qik.ctx.format(self.extra_index_url)

    @qik.func.cached_property
    def resolved_cache(self) -> str:
        return qik.ctx.format(
            qik.unset.coalesce(self.cache, qik.conf.project().defaults.cache, default="repo")
        )


qik.conf.register_type(UVVenvConf, "qik.uv.venv.factory")
qik.conf.register_conf(UVPluginConf)
