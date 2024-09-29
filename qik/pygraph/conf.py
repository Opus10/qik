from __future__ import annotations

from typing import TYPE_CHECKING

import qik.conf
import qik.func
import qik.pygraph.qikplugin

if TYPE_CHECKING:
    from qik.pygraph.qikplugin import PygraphPluginConf


@qik.func.cache
def get() -> PygraphPluginConf:
    """Get the pygraph config."""
    return qik.conf.plugin("qik.pygraph")  # type: ignore
