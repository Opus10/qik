from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Iterator

import msgspec

import qik.conf
import qik.dep
import qik.errors
import qik.file
import qik.func
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

    @qik.func.cached_property
    def watch(self) -> list[str]:
        return [qik.conf.location().name]

    @qik.func.cached_property
    def vals(self) -> list[str]:  # type: ignore
        return [str(msgspec.json.encode(qik.conf.project().pygraph))]


@qik.func.cache
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


def lock_cmd(runnable: qik.runnable.Runnable) -> tuple[int, str]:
    pyimport = runnable.args.get("pyimport")
    if not pyimport:
        raise AssertionError("Unexpected qik.pygraph.lock runnable.")

    graph = load_graph()
    # TODO: Better error if the module doesn't exist
    upstream = graph.upstream_modules(pyimport, idx=False)
    root = graph.modules[graph.modules_idx[pyimport]]
    distributions = runnable.venv.packages_distributions()

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

    runnable.store_deps(
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
    if "pyimport" not in args or "space" not in args:
        raise qik.errors.ArgNotSupplied(
            '"pyimport" and "space" args are required for qik.pygraph.lock command.'
        )

    pyimport = args["pyimport"]
    space = args["space"]
    name = f"{lock_cmd_name()}?pyimport={pyimport}"
    if space:
        name += f"&space={space}"

    cmd_name = lock_cmd_name()
    artifact = str(lock_path(pyimport))
    runnable = qik.runnable.Runnable(
        name=name,
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
        space=space,
        args={"pyimport": pyimport},
    )
    return {runnable.name: runnable}


@qik.func.cache
def build_cmd_name() -> str:
    graph_plugin_name = qik.conf.plugin_locator("qik.pygraph", by_pyimport=True).name
    return f"{graph_plugin_name}.build"


@qik.func.cache
def lock_cmd_name() -> str:
    graph_plugin_name = qik.conf.plugin_locator("qik.pygraph", by_pyimport=True).name
    return f"{graph_plugin_name}.lock"


@qik.func.cache
def graph_path() -> pathlib.Path:
    return qik.conf.pub_work_dir() / "artifacts" / build_cmd_name() / "graph.json"


@qik.func.cache
def lock_path(pyimport: str) -> pathlib.Path:
    return qik.conf.pub_work_dir() / "artifacts" / lock_cmd_name() / f"lock.{pyimport}.json"


@qik.func.per_run_cache
def load_graph() -> qik.pygraph.core.Graph:
    """Load the graph."""
    return msgspec.json.decode(graph_path().read_bytes(), type=qik.pygraph.core.Graph)
