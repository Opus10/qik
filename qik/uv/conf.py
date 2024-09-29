from __future__ import annotations

from typing import TYPE_CHECKING

import qik.conf
import qik.func
import qik.uv.qikplugin

if TYPE_CHECKING:
    from qik.uv.qikplugin import UVPluginConf


@qik.func.cache
def get() -> UVPluginConf:
    """Get the uv config."""
    return qik.conf.plugin("qik.uv")  # type: ignore
