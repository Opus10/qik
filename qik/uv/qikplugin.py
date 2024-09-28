import qik.conf
import qik.func
import qik.unset


class UVVenvConf(qik.conf.Venv, frozen=True, tag="uv"):
    python: str | None = None


class UVPluginConf(qik.conf.Base, frozen=True, dict=True):
    cache: str | qik.unset.UnsetType = qik.unset.UNSET

    @qik.func.cached_property
    def resolved_cache(self) -> str:
        return qik.unset.coalesce(self.cache, qik.conf.defaults().cache, default="repo", type=str)


qik.conf.register_type(UVVenvConf, "qik.uv.venv.factory")
qik.conf.register_conf(UVPluginConf, "qik.uv")
