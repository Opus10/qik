from __future__ import annotations

from typing import TYPE_CHECKING

import qik.conf
import qik.func
import qik.pygraph.conf

if TYPE_CHECKING:
    import pathlib


@qik.func.cache
def build_cmd_name() -> str:
    graph_plugin_name = qik.conf.plugin_locator("qik.pygraph", by_pyimport=True).name
    return f"{graph_plugin_name}.build"


@qik.func.cache
def lock_cmd_name() -> str:
    graph_plugin_name = qik.conf.plugin_locator("qik.pygraph", by_pyimport=True).name
    return f"{graph_plugin_name}.lock"


@qik.func.cache
def check_cmd_name() -> str:
    graph_plugin_name = qik.conf.plugin_locator("qik.pygraph", by_pyimport=True).name
    return f"{graph_plugin_name}.check"


@qik.func.cache
def graph_path() -> pathlib.Path:
    pygraph_conf = qik.pygraph.conf.get()
    root = (
        qik.conf.pub_work_dir() if pygraph_conf.build_cache == "repo" else qik.conf.priv_work_dir()
    )
    return root / "artifacts" / build_cmd_name() / "graph.json"


@qik.func.cache
def lock_path(pyimport: str, space: str | None = None) -> pathlib.Path:
    pygraph_conf = qik.pygraph.conf.get()
    root = (
        qik.conf.pub_work_dir() if pygraph_conf.lock_cache == "repo" else qik.conf.priv_work_dir()
    )
    file_name = f"lock.{pyimport}.{space}.json" if space else f"lock.{pyimport}.json"
    return root / "artifacts" / lock_cmd_name() / file_name
