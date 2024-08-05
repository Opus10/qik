from __future__ import annotations

import collections
import concurrent.futures
import copy
import functools
import pathlib
import sys
from typing import TYPE_CHECKING, Iterable, Iterator, Literal, TypeAlias

from typing_extensions import Self

import qik.cmd
import qik.conf
import qik.console
import qik.ctx
import qik.dep
import qik.logger
import qik.runnable
import qik.shell
import qik.unset
import qik.venv
import qik.watcher

if TYPE_CHECKING:
    from qik.cache import Entry
    from qik.runnable import Result, Runnable

    Direction: TypeAlias = Literal["up", "down"]
    Edges: TypeAlias = dict[str, set[str]]


class DAGPool:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.nodes = graph.nodes
        self.upstream = graph.upstream

        runner = qik.ctx.runner()
        self.pool = runner.pool
        self.logger = runner.logger
        self.downstream = collections.defaultdict(set)
        for node, deps in graph.upstream.items():
            for dep in deps:
                self.downstream[dep].add(node)

    def _exec(self) -> dict[str, Result | None]:
        in_degree = {name: len(deps) for name, deps in self.upstream.items()}
        results: dict[str, Result | None] = {}
        failed: set[str] = set()
        futures: dict[str, concurrent.futures.Future] = {}

        def _skip(name: str):
            del in_degree[name]
            failed.add(name)
            results[name] = None
            self.logger.print(
                msg=f"{name} [default][dim]{self.nodes[name].val}",
                emoji="heavy_minus_sign",
                color="yellow",
                runnable=self.nodes[name],
                event="finish",
                result=None,
            )

        def _finish(future: concurrent.futures.Future):
            name = next(name for name, val in futures.items() if val == future)
            try:
                result: Result = future.result()
            except Exception:
                failed.add(name)
                self.logger.print(
                    "An unexpected error happened.",
                    emoji="broken_heart",
                    color="red",
                    event="exception",
                )
                sys.exit(1)

            results[name] = result
            if result.code != 0:
                failed.add(name)
                for dep in self.downstream[name]:
                    _skip(dep)
            else:
                for dep in self.downstream[name]:
                    in_degree[dep] -= 1

            del in_degree[name]
            del futures[name]

        while in_degree:
            ready_tasks = (name for name, degree in in_degree.items() if degree == 0)
            for name in ready_tasks:
                if name not in futures:
                    if not any(dep in failed for dep in self.upstream[name]):
                        futures[name] = self.pool.submit(self.nodes[name].exec)
                    else:
                        _skip(name)

            finished, unfinished = concurrent.futures.wait(
                futures.values(), return_when=concurrent.futures.FIRST_COMPLETED
            )
            if not finished and not unfinished:
                break

            for future in finished:
                _finish(future)

        for name, future in futures.items():
            future.cancel()
            results[name] = None

        return results

    def exec(self) -> dict[str, Result | None]:
        if not self.nodes:
            return {}
        else:
            with self.logger.run(self.graph):
                return self._exec()


class Graph:
    """A graph of runnables."""

    def __init__(self, cmds: Iterable[str]):
        self.cmds = cmds
        self._view = None

        # Construct the graph
        self._nodes: dict[str, Runnable] = {
            name: runnable
            for cmd in cmds
            for name, runnable in qik.cmd.load(cmd).runnables.items()
        }
        self._graph = {
            "up": collections.defaultdict(set[str]),
            "down": collections.defaultdict(set[str]),
        }

        def _runnable_edges(runnable: Runnable) -> Iterator[tuple[Runnable, Runnable, Direction]]:
            """Given a runnable, iterate over all of its edges."""
            for dep in runnable.deps_collection.runnables.values():
                isolated = (
                    dep.isolated
                    if dep.isolated is not qik.unset.UNSET
                    else qik.ctx.module("qik").isolated
                )
                if not isolated or dep.obj.name in self._nodes:
                    yield (runnable, dep.obj, "up")
                    if dep.strict:
                        yield (dep.obj, runnable, "down")

                    yield from _runnable_edges(dep.obj)

        def _runnables_edges() -> Iterator[tuple[Runnable, Runnable, Direction]]:
            for runnable in self._nodes.values():
                yield from _runnable_edges(runnable)

        edges = list(_runnables_edges())
        for src, dest, direction in edges:
            self._graph[direction][src.name].add(dest.name)
            self._nodes[src.name] = src
            self._nodes[dest.name] = dest

    def _dfs(self, start_node: str, direction: Direction) -> set[str]:
        def _dfs_trav(node: str) -> Iterator[str]:
            for name in self._graph[direction][node]:
                yield name
                yield from _dfs_trav(name)

        return set(_dfs_trav(start_node))

    @functools.cached_property
    def _upstream(self) -> Edges:
        return {name: self._dfs(name, "up") for name in self.nodes}

    @functools.cached_property
    def _downstream(self) -> Edges:
        return {name: self._dfs(name, "down") for name in self.nodes}

    ###
    # Filtering methods and filtered properties
    ###

    def filter_cache_types(self, cache_types: list[str]) -> Self:
        """Filter the graph by the type of cache."""
        cache_types_set = frozenset(c_type.lower() for c_type in cache_types)
        return self.filter(
            runnable for runnable in self if runnable.get_cache_backend().type in cache_types_set
        )

    def filter_cache_status(self, cache_status: qik.conf.CacheStatus) -> Self:
        """Filter the graph by cache status."""

        def _matches_cache_status(entry: Entry | None) -> bool:
            return bool(entry) if cache_status == "warm" else not bool(entry)

        return self.filter(
            runnable for runnable in self if _matches_cache_status(runnable.get_cache_entry())
        )

    def filter_since(self, git_sha: str) -> Self:
        """Filter the graph since a git SHA"""
        project_dir = qik.conf.root()
        git_dir = pathlib.Path(
            qik.shell.exec("git rev-parse --show-toplevel", check=True).stdout.strip()
        )
        diff_files = qik.shell.exec(f"git diff --name-only {git_sha} -- .", check=True, lines=True)

        # Remember, names from git diff will include folders not in our
        # project root. Make all names relative to the project root
        changes = [
            qik.dep.Glob(str((git_dir / diff_file).relative_to(project_dir)))
            for diff_file in diff_files
        ]

        return self.filter_changes(changes, strategy="since")

    def filter_changes(
        self, deps: Iterable[qik.dep.BaseDep], strategy: qik.runnable.FilterStrategy
    ) -> Self:
        """Filter the graph by a list of changed dependencies."""
        runnables: dict[str, Runnable] = {}
        globs = "\n".join(change.val for change in deps if isinstance(change, qik.dep.Glob))
        if globs:
            runnables |= {
                runnable.name: runnable
                for runnable in self
                if (regex := runnable.filter_regex(strategy)) and regex.search(globs)
            }

        dists = {change.val for change in deps if isinstance(change, qik.dep.Dist)}
        if dists:
            runnables |= {
                runnable.name: runnable
                for runnable in self
                if set(runnable.deps_collection.dists) & dists
            }

        return self.filter(runnables.values())

    def filter_modules(self, modules: list[str]) -> Self:
        """Filter the graph by a list of modules."""
        modules_set = frozenset(modules)
        return self.filter(
            runnable for runnable in self if not runnable.module or runnable.module in modules_set
        )

    def filter(self, runnables: Iterable[Runnable]) -> Self:
        """Return a filtered graph. Include upstream and downstream runnables."""
        clone = copy.copy(self)
        clone._view = {runnable.name for runnable in runnables if runnable.name in self._nodes}
        clone._view |= {dep for runnable in clone._view for dep in self._upstream[runnable]}
        clone._view |= {dep for runnable in clone._view for dep in self._downstream[runnable]}

        if "nodes" in clone.__dict__:
            del clone.__dict__["nodes"]

        if "upstream" in clone.__dict__:
            del clone.__dict__["upstream"]

        return clone

    @functools.cached_property
    def upstream(self) -> Edges:
        return {
            name: {dep for dep in deps if self._view is None or dep in self._view}
            for name, deps in self._upstream.items()
            if self._view is None or name in self._view
        }

    @functools.cached_property
    def nodes(self) -> dict[str, Runnable]:
        return {
            name: runnable
            for name, runnable in self._nodes.items()
            if self._view is None or name in self._view
        }

    def __len__(self) -> int:
        return len(self.nodes)

    def __iter__(self) -> Iterator[Runnable]:
        return iter(self.nodes.values())

    def __getitem__(self, name: str) -> Runnable:
        return self.nodes[name]


class Runner:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=qik.ctx.module("qik").workers
        )
        qik_ctx = qik.ctx.module("qik")
        self.logger = (
            qik.logger.Stdout()
            if len(graph) == 1 or qik_ctx.workers == 1
            else qik.logger.Progress()
        )

    def exec(self, *, changes: Iterable[qik.dep.BaseDep] | None = None) -> int:
        """Exec the runner, optionally providing a list of changed dependencies."""
        orig_graph = self.graph
        self.graph = (
            self.graph.filter_changes(changes, strategy="watch") if changes else self.graph
        )
        results = DAGPool(graph=self.graph).exec()
        self.graph = orig_graph
        return max((result.code for result in results.values() if result), default=0)

    def watch(self) -> None:
        self.logger.print("Watching for changes...", emoji="eyes", color="cyan")
        qik.watcher.start(self)


def exec() -> Graph:
    """Run commands based on the current qik context."""
    qik_ctx = qik.ctx.module("qik")
    cmds = qik_ctx.commands
    modules = qik_ctx.modules

    if not cmds:
        cmds = [cmd.name for cmd in qik.cmd.ls()]

    try:
        graph = Graph(cmds)
    except RecursionError:
        qik.console.print("Cycle detected in DAG.", emoji="broken_heart", color="red")
        sys.exit(1)

    if qik_ctx.cache_types:
        graph = graph.filter_cache_types(qik_ctx.cache_types)

    if qik_ctx.cache_status:
        graph = graph.filter_cache_status(qik_ctx.cache_status)

    if qik_ctx.since:
        graph = graph.filter_since(qik_ctx.since)

    if qik_ctx.modules:
        graph = graph.filter_modules(modules)

    if not qik_ctx.ls and not qik_ctx.fail:
        runner = Runner(graph=graph)
        with qik.ctx.set_runner(runner):
            exit_code = runner.exec()

            if qik_ctx.watch:
                runner.watch()
            else:
                sys.exit(exit_code)

    return graph
