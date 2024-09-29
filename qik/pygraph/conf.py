from __future__ import annotations

from typing import TYPE_CHECKING

import qik.conf
import qik.func

if TYPE_CHECKING:
    from qik.pygraph.qikplugin import PygraphPluginConf


@qik.func.cache
def get() -> PygraphPluginConf:
    """Get the pygraph config."""
    proj = qik.conf.project()
    return getattr(proj.conf, proj.plugins_by_pyimport["qik.pygraph"][0])  # type: ignore
