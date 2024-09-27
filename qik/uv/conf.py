from __future__ import annotations

from typing import TYPE_CHECKING

import qik.conf
import qik.func

if TYPE_CHECKING:
    from qik.uv.qikplugin import UVPluginConf


@qik.func.cache
def get() -> UVPluginConf:
    """Get the uv config."""
    proj = qik.conf.project()
    return getattr(proj.conf.plugins, proj.plugins_by_pyimport["qik.uv"].name)  # type: ignore
