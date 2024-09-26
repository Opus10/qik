from __future__ import annotations

import qik.conf


class PygraphDepConf(qik.conf.Dep, tag="pygraph", frozen=True):
    pyimport: str


class PygraphPluginConf(qik.conf.Base, frozen=True):
    ignore_type_checking: bool = False
    ignore_pydists: bool = False
    ignore_missing_module_pydists: bool = False
    module_pydists: dict[str, str] = {}


qik.conf.register_type(PygraphDepConf, "qik.pygraph.dep.factory")
qik.conf.register_conf(PygraphPluginConf, "qik.pygraph")
