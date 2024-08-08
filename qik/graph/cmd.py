from __future__ import annotations

import functools
import importlib.metadata
import os
import pathlib
import sysconfig
import threading
from typing import TYPE_CHECKING, Iterator

import msgspec

import qik.conf
import qik.dep
import qik.file
import qik.graph.core
import qik.hash
import qik.runnable

if TYPE_CHECKING:
    import grimp.exceptions as grimp_exceptions
else:
    import qik.lazy

    grimp_exceptions = qik.lazy.module("grimp.exceptions")


class GraphConfDep(qik.dep.Val, frozen=True, dict=True):
    val: str = "graph"
    file: str = ""  # The file is dynamic based on config location

    @functools.cached_property
    def watch(self) -> list[str]:
        return [qik.conf.location().name]

    # TODO: break this cache on runner invocations
    @functools.cached_property
    def vals(self) -> list[str]:
        return [str(msgspec.json.encode(qik.conf.project().graph))]


@functools.cache
def _graph_conf_dep() -> qik.dep.Val:
    """Serialize the graph config so it can be included as a dependency."""
    return GraphConfDep()


def build_cmd(runnable: qik.runnable.Runnable) -> tuple[int, str]:
    """Build the graph."""
    try:
        graph = qik.graph.core.build()
    except grimp_exceptions.SourceSyntaxError as exc:
        return 1, f"Cannot build import graph - {exc}"

    path = graph_path()

    serialized = msgspec.json.encode(graph)
    qik.file.write(path, serialized)
    return 0, ""


class PackagesDistributions(msgspec.Struct):
    venv_hash: str
    packages_distributions: dict[str, list[str]]


@functools.lru_cache(maxsize=1)
def _packages_distributions(venv_hash: str) -> dict[str, list[str]]:
    cache_path = qik.conf.priv_work_dir() / "graph" / "packages_distributions.json"
    try:
        cached_val = msgspec.json.decode(cache_path.read_bytes(), type=PackagesDistributions)
        if cached_val.venv_hash == venv_hash:
            return cached_val.packages_distributions
    except FileNotFoundError:
        pass

    cached_val = PackagesDistributions(
        venv_hash=venv_hash, packages_distributions=importlib.metadata.packages_distributions()
    )
    qik.file.write(cache_path, msgspec.json.encode(cached_val))

    return cached_val.packages_distributions


_PACKAGES_DISTRIBUTIONS_LOCK = threading.Lock()


def packages_distributions() -> dict[str, list[str]]:
    """Obtain a mapping of modules to their associated dists.

    This is an expensive command, so use an underlying cache when possible.
    """
    venv_hash = qik.hash.strs(*os.listdir(sysconfig.get_path("purelib")))
    with _PACKAGES_DISTRIBUTIONS_LOCK:
        return _packages_distributions(venv_hash)


def analyze_cmd(runnable: qik.runnable.Runnable) -> tuple[int, str]:
    if not runnable.module:
        raise AssertionError("Unexpected analyze runnable.")

    graph = load_graph()  # TODO: Use cached runner graph
    # TODO: Better error if the module doesn't exist
    module = qik.conf.project().modules_by_name[runnable.module]
    upstream = graph.upstream_modules(module.path, idx=False)
    root = graph.modules[graph.modules_idx[module.path]]
    distributions = packages_distributions()

    def _gen_upstream_globs() -> Iterator[str]:
        for module in [root, *upstream]:
            if module.is_internal:
                path = module.imp.replace(".", "/")
                yield f"{path}/**.py"
                yield f"{path}.py"

    def _gen_upstream_dists() -> Iterator[str]:
        for module in upstream:
            if not module.is_internal:
                yield from distributions[module.imp]

    qik.dep.store(
        analysis_path(module.name),
        globs=sorted(_gen_upstream_globs()),
        dists=sorted(_gen_upstream_dists()),
    )
    return 0, ""


def build_cmd_factory(cmd: str, conf: qik.conf.CmdConf) -> dict[str, qik.runnable.Runnable]:
    build_graph_cmd_name = build_cmd_name()
    runnable = qik.runnable.Runnable(
        name=build_graph_cmd_name,
        cmd=build_graph_cmd_name,
        val="qik.graph.cmd.build_cmd",
        shell=False,
        deps=[qik.dep.Glob("**.py"), _graph_conf_dep(), *qik.dep.project_deps()],
        artifacts=[str(graph_path())],
        cache="repo",
    )
    return {runnable.name: runnable}


def analyze_cmd_factory(cmd: str, conf: qik.conf.CmdConf) -> dict[str, qik.runnable.Runnable]:
    cmd_name = analyze_cmd_name()
    build_graph_dep = qik.dep.Cmd(build_cmd_name())

    runnables = [
        qik.runnable.Runnable(
            name=f"{cmd_name}@{module.name}",
            cmd=cmd_name,
            val="qik.graph.cmd.analyze_cmd",
            shell=False,
            deps=[
                build_graph_dep,
                qik.dep.Load(
                    str(analysis_path(module.name)),
                    default=["**.py"],
                ),
                _graph_conf_dep(),
                *qik.dep.project_deps(),
            ],
            artifacts=[str(analysis_path(module.name))],
            module=module.name,
            cache="repo",
        )
        for module in qik.conf.project().modules_by_name.values()
    ]

    return {runnable.name: runnable for runnable in runnables}


@functools.cache
def build_cmd_name() -> str:
    graph_plugin_name = qik.conf.path_to_name("qik.graph")
    return f"{graph_plugin_name}.build"


@functools.cache
def analyze_cmd_name() -> str:
    graph_plugin_name = qik.conf.path_to_name("qik.graph")
    return f"{graph_plugin_name}.analyze"


@functools.cache
def graph_path() -> pathlib.Path:
    return qik.conf.pub_work_dir(relative=True) / "artifacts" / build_cmd_name() / "graph.json"


@functools.cache
def analysis_path(module: str) -> pathlib.Path:
    return (
        qik.conf.pub_work_dir(relative=True)
        / "artifacts"
        / analyze_cmd_name()
        / f"analzye.{module}.json"
    )


def load_graph() -> qik.graph.core.Graph:
    """Load the graph."""
    return msgspec.json.decode(graph_path().read_bytes(), type=qik.graph.core.Graph)
