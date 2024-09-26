from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable, Iterator

import msgspec

import qik.conf
import qik.dep
import qik.errors
import qik.file
import qik.func
import qik.hash
import qik.pygraph.conf
import qik.pygraph.core
import qik.pygraph.utils
import qik.runnable
import qik.space

if TYPE_CHECKING:
    import grimp.exceptions as grimp_exceptions
else:
    import qik.lazy

    grimp_exceptions = qik.lazy.module("grimp.exceptions")


class GraphConfDep(qik.dep.Val, frozen=True, dict=True):
    val: str = "pygraph"  # The value is dynamic based on plugin name
    file: str = ""  # The file is dynamic based on config location

    @qik.func.cached_property
    def watch(self) -> list[str]:
        return [qik.conf.location().name]

    @qik.func.cached_property
    def vals(self) -> list[str]:  # type: ignore
        conf = qik.pygraph.conf.get()
        return [str(msgspec.json.encode(conf))]


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

    path = qik.pygraph.utils.graph_path()

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
        qik.pygraph.utils.lock_path(pyimport, runnable.space),
        globs=sorted(_gen_upstream_globs()),
        pydists=sorted(_gen_upstream_pydists()),
    )
    return 0, ""


def _generate_fence_regex(imps: Iterable[str]) -> re.Pattern:
    escaped_substrings = (re.escape(s) for s in imps)
    pattern = "|".join(escaped_substrings)
    return re.compile(f"^(?!({pattern})).*$", re.MULTILINE)


def check_cmd(runnable: qik.runnable.Runnable) -> tuple[int, str]:
    graph = load_graph()
    # TODO: Handle custom PYTHONPATH env var
    fence_imps = [f.replace("/", ".") for f in runnable.space_obj.conf.fence]
    imps: set[tuple[qik.pygraph.core.Module, qik.pygraph.core.Module]] = set().union(
        *(graph.upstream_imports(imp) for imp in fence_imps)
    )

    internal_imps = "\n".join(
        f"{dest.imp} imported from {src.imp}" for src, dest in imps if dest.is_internal
    )
    internal_fence_re = _generate_fence_regex(fence_imps)
    internal_violations = [
        violation.group() for violation in re.finditer(internal_fence_re, internal_imps)
    ]

    external_imps = "\n".join(
        f"{dest.imp} imported from {src.imp}" for src, dest in imps if not dest.is_internal
    )
    external_fence_re = _generate_fence_regex(
        (external_imp for external_imp, _ in runnable.venv.packages_distributions().items())
    )
    external_violations = [
        violation.group() for violation in re.finditer(external_fence_re, external_imps)
    ]

    ret_code = 0 if not internal_violations and not external_violations else 1
    if ret_code == 1:
        stdout = ""
        if internal_violations:
            stdout += (
                f'Found {len(internal_violations)} internal import violations for "{runnable.space}" space:\n'
                + "\n".join(internal_violations)
            ) + "\n\n"
        if external_violations:
            stdout += (
                f'Found {len(external_violations)} external import violations for "{runnable.space}" space:\n'
                + "\n".join(external_violations)
            )
    else:
        stdout = (
            f'No import violations found across {len(imps)} imports in "{runnable.space}" space'
        )

    return ret_code, stdout.strip()


def build_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    build_graph_cmd_name = qik.pygraph.utils.build_cmd_name()
    runnable = qik.runnable.Runnable(
        name=build_graph_cmd_name,
        cmd=build_graph_cmd_name,
        val="qik.pygraph.cmd.build_cmd",
        shell=False,
        deps=[qik.dep.Glob("**.py"), _graph_conf_dep(), *qik.dep.project_deps()],
        artifacts=[str(qik.pygraph.utils.graph_path())],
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
    name = f"{qik.pygraph.utils.lock_cmd_name()}?pyimport={pyimport}"
    if space:
        name += f"&space={space}"

    cmd_name = qik.pygraph.utils.lock_cmd_name()
    artifact = str(qik.pygraph.utils.lock_path(pyimport, space))
    runnable = qik.runnable.Runnable(
        name=name,
        cmd=cmd_name,
        val="qik.pygraph.cmd.lock_cmd",
        shell=False,
        deps=[
            qik.dep.Cmd(qik.pygraph.utils.build_cmd_name()),
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


def check_cmd_factory(
    cmd: str, conf: qik.conf.Cmd, **args: str
) -> dict[str, qik.runnable.Runnable]:
    cmd_name = qik.pygraph.utils.check_cmd_name()
    return {
        f"{cmd_name}#{space}": qik.runnable.Runnable(
            name=f"{cmd_name}#{space}",
            cmd=cmd_name,
            val="qik.pygraph.cmd.check_cmd",
            shell=False,
            deps=[
                qik.dep.Cmd(qik.pygraph.utils.build_cmd_name()),
                *(qik.dep.Glob(fence_val) for fence_val in conf.fence),
            ],
            cache=None,
            space=space,
        )
        for space, conf in qik.conf.project().spaces.items()
        if conf.fence
    }


@qik.func.per_run_cache
def load_graph() -> qik.pygraph.core.Graph:
    """Load the graph."""
    return msgspec.json.decode(
        qik.pygraph.utils.graph_path().read_bytes(), type=qik.pygraph.core.Graph
    )
