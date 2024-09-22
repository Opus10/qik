from __future__ import annotations

import qik.conf


class PygraphDepConf(qik.conf.Dep, tag="pygraph", frozen=True):
    pyimport: str


qik.conf.register_type(PygraphDepConf, "qik.pygraph.dep.factory")
