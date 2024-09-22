from __future__ import annotations

from typing import TYPE_CHECKING

import qik.conf
import qik.func

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
    return qik.conf.pub_work_dir() / "artifacts" / build_cmd_name() / "graph.json"


@qik.func.cache
def lock_path(pyimport: str) -> pathlib.Path:
    return qik.conf.pub_work_dir() / "artifacts" / lock_cmd_name() / f"lock.{pyimport}.json"
