import qik.conf


class UVConf(qik.conf.Venv, frozen=True, tag="uv"):
    python: str | None = None


qik.conf.register_type(UVConf, "qik.uv.venv.factory")
