from __future__ import annotations

import collections
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
import qik.errors
import qik.file
import qik.hash
import qik.pygraph.core
import qik.runnable

if TYPE_CHECKING:
    import grimp.exceptions as grimp_exceptions
else:
    import qik.lazy

    grimp_exceptions = qik.lazy.module("grimp.exceptions")


class GraphConfDep(qik.dep.Val, frozen=True, dict=True):
    val: str = "pygraph"
    file: str = ""  # The file is dynamic based on config location

    @functools.cached_property
    def watch(self) -> list[str]:
        return [qik.conf.location().name]

    # TODO: break this cache on runner invocations
    @functools.cached_property
    def vals(self) -> list[str]:  # type: ignore
        return [str(msgspec.json.encode(qik.conf.project().pygraph))]


@functools.cache
def _graph_conf_dep() -> qik.dep.Val:
    """Serialize the graph config so it can be included as a dependency."""
    return GraphConfDep()


def build_cmd(runnable: qik.runnable.Runnable) -> tuple[int, str]:
    """Build the import graph."""
    try:
        graph = qik.pygraph.core.build()
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
    pygraph_conf = qik.conf.project().pygraph
    cache_path = qik.conf.priv_work_dir() / "pygraph" / "packages_distributions.json"
    overrides = (
        {}
        if not pygraph_conf.ignore_missing_module_pydists
        else collections.defaultdict(lambda: [""])
    )
    overrides |= {module: [dist] for module, dist in pygraph_conf.module_pydists.items()}
    try:
        cached_val = msgspec.json.decode(cache_path.read_bytes(), type=PackagesDistributions)
        if cached_val.venv_hash == venv_hash:
            return overrides | cached_val.packages_distributions
    except FileNotFoundError:
        pass

    cached_val = PackagesDistributions(
        venv_hash=venv_hash,
        packages_distributions=importlib.metadata.packages_distributions(),  # type: ignore
    )
    qik.file.write(cache_path, msgspec.json.encode(cached_val))

    return overrides | cached_val.packages_distributions


_PACKAGES_DISTRIBUTIONS_LOCK = threading.Lock()


def packages_distributions() -> dict[str, list[str]]:
    """Obtain a mapping of modules to their associated python distributions.

    This is an expensive command, so use an underlying cache when possible.
    """
    venv_hash = qik.hash.strs(*os.listdir(sysconfig.get_path("purelib")))
    with _PACKAGES_DISTRIBUTIONS_LOCK:
        return _packages_distributions(venv_hash)


def lock_cmd(runnable: qik.runnable.Runnable) -> tuple[int, str]:
    pyimport = runnable.args.get("pyimport")
    if not pyimport:
        raise AssertionError("Unexpected qik.pygraph.deps runnable.")

    graph = load_graph()  # TODO: Use cached runner graph
    # TODO: Better error if the module doesn't exist
    upstream = graph.upstream_modules(pyimport, idx=False)
    root = graph.modules[graph.modules_idx[pyimport]]
    distributions = packages_distributions()

    def _gen_upstream_globs() -> Iterator[str]:
        for module in [root, *upstream]:
            if module.is_internal:
                path = module.imp.replace(".", "/")
                yield f"{path}/**.py"
                yield f"{path}.py"

    def _gen_upstream_pydists() -> Iterator[str]:
        for module in upstream:
            if not module.is_internal:
                try:
                    yield from (pydist for pydist in distributions[module.imp] if pydist)
                except KeyError as exc:
                    raise qik.errors.DistributionNotFound(
                        f'No distribution found for module "{module.imp}"'
                    ) from exc

    qik.dep.store(
        lock_path(pyimport),
        globs=sorted(_gen_upstream_globs()),
        pydists=sorted(_gen_upstream_pydists()),
    )
    return 0, ""


def build_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    build_graph_cmd_name = build_cmd_name()
    runnable = qik.runnable.Runnable(
        name=build_graph_cmd_name,
        cmd=build_graph_cmd_name,
        val="qik.pygraph.cmd.build_cmd",
        shell=False,
        deps=[qik.dep.Glob("**.py"), _graph_conf_dep(), *qik.dep.project_deps()],
        artifacts=[str(graph_path())],
        cache="repo",
    )
    return {runnable.name: runnable}


def lock_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    pyimport = args.get("pyimport")
    if not pyimport:
        raise qik.errors.ArgNotSupplied('"pyimport" arg is required for qik.pygraph.deps command.')

    cmd_name = lock_cmd_name()
    artifact = str(lock_path(pyimport))

    runnable = qik.runnable.Runnable(
        name=f"{cmd_name}?pyimport={pyimport}",
        cmd=cmd_name,
        val="qik.pygraph.cmd.lock_cmd",
        shell=False,
        deps=[
            qik.dep.Cmd(build_cmd_name()),
            qik.dep.Load(artifact, default=["**.py"]),
            _graph_conf_dep(),
            *qik.dep.project_deps(),
        ],
        artifacts=[artifact],
        cache="repo",
        args={"pyimport": pyimport},
    )
    return {runnable.name: runnable}


@functools.cache
def build_cmd_name() -> str:
    graph_plugin_name = qik.conf.plugin_locator("qik.pygraph", by_pyimport=True).name
    return f"{graph_plugin_name}.build"


@functools.cache
def lock_cmd_name() -> str:
    graph_plugin_name = qik.conf.plugin_locator("qik.pygraph", by_pyimport=True).name
    return f"{graph_plugin_name}.lock"


@functools.cache
def graph_path() -> pathlib.Path:
    return qik.conf.pub_work_dir(relative=True) / "artifacts" / build_cmd_name() / "graph.json"


@functools.cache
def lock_path(imp: str) -> pathlib.Path:
    return (
        qik.conf.pub_work_dir(relative=True) / "artifacts" / lock_cmd_name() / f"lock.{imp}.json"
    )


def load_graph() -> qik.pygraph.core.Graph:
    """Load the graph."""
    return msgspec.json.decode(graph_path().read_bytes(), type=qik.pygraph.core.Graph)
