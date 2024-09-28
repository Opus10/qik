"""Functions and classes for managing and serializing the import graph for a module."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import pkgutil
import sys
from typing import TYPE_CHECKING, Iterator, Literal, overload

import msgspec
from typing_extensions import Self

import qik.conf
import qik.ctx
import qik.dep
import qik.func
import qik.pygraph.conf
import qik.shell

if TYPE_CHECKING:
    import grimp
    import rustworkx as rx
else:
    import qik.lazy

    grimp = qik.lazy.module("grimp")
    rx = qik.lazy.module("rustworkx")


class Module(msgspec.Struct, array_like=True, omit_defaults=True, frozen=True, dict=True):
    imp: str
    is_internal: bool = True

    @qik.func.cached_property
    def path(self) -> str:
        return self.imp.replace(".", "/")


class Graph(msgspec.Struct, frozen=True, dict=True):
    modules: list[Module]
    edges: list[tuple[int, int]]

    def bind(self, rx_graph: rx.PyDiGraph) -> Self:
        self.__dict__["_rx"] = rx_graph
        return self

    @property
    def rx(self) -> rx.PyDiGraph:
        if "_rx" not in self.__dict__:
            g = rx.PyDiGraph()
            g.add_nodes_from(self.modules)
            g.add_edges_from_no_data(self.edges)
            self.__dict__["_rx"] = g

        return self.__dict__["_rx"]

    @qik.func.cached_property
    def modules_idx(self) -> dict[str, int]:
        return {module.imp: i for i, module in enumerate(self.modules)}

    @overload
    def upstream_imports(self, imp: str, /, *, idx: Literal[True]) -> list[tuple[int, int]]: ...

    @overload
    def upstream_imports(
        self, imp: str, /, *, idx: Literal[False]
    ) -> list[tuple[Module, Module]]: ...

    @overload
    def upstream_imports(self, imp: str, /) -> list[tuple[Module, Module]]: ...

    @overload
    def upstream_imports(
        self, imp: str, /, *, idx: bool = ...
    ) -> list[tuple[Module, Module]] | list[tuple[int, int]]: ...

    def upstream_imports(
        self, imp: str, /, *, idx: bool = False
    ) -> list[tuple[Module, Module]] | list[tuple[int, int]]:
        upstream = rx.digraph_dfs_edges(self.rx, self.modules_idx[imp])
        if idx:
            return list(upstream)
        else:
            modules = self.modules
            return [(modules[edge[0]], modules[edge[1]]) for edge in upstream]

    @overload
    def upstream_modules(self, imp: str, /, *, idx: Literal[True]) -> set[int]: ...

    @overload
    def upstream_modules(self, imp: str, /, *, idx: Literal[False]) -> set[Module]: ...

    def upstream_modules(self, imp: str, /, *, idx: bool = False) -> set[Module] | set[int]:
        return {imp[1] for imp in self.upstream_imports(imp, idx=idx)}  # type: ignore


def build() -> Graph:
    """Build the import graph from the current codebase."""
    python_path = str(qik.conf.abs_python_path())
    internal_modules = {
        module.name
        for module in pkgutil.iter_modules()
        if module.ispkg
        and isinstance(module.module_finder, importlib.machinery.FileFinder)
        and module.module_finder.path == python_path
    }
    # TODO: Raise a runtime error if no internalmodules were found. Suggest to configure the python path.
    stdlib_modules = sys.stdlib_module_names | set(sys.builtin_module_names)

    # Parse the codebase with grimp
    pygraph_conf = qik.pygraph.conf.get()
    grimp_g = grimp.build_graph(
        *internal_modules,
        include_external_packages=not pygraph_conf.ignore_pydists,
        exclude_type_checking_imports=pygraph_conf.ignore_type_checking,
        cache_dir=str(qik.conf.priv_work_dir() / ".grimp"),
    )
    graph_modules_imps = [(imp.split(".", 1)[0], imp) for imp in sorted(grimp_g.modules)]
    modules = [
        Module(imp=imp, is_internal=module in internal_modules)
        for module, imp in graph_modules_imps
        if module not in stdlib_modules
    ]
    modules_idx = {module.imp: i for i, module in enumerate(modules)}

    # Start constructing the rustworkx graph
    rx_g = rx.PyDiGraph()
    rx_g.add_nodes_from(modules)

    # Add layered modules as dependencies on one another for graph locking
    def _iter_layered_module_edges() -> Iterator[tuple[int, int]]:
        for i, module in enumerate(modules):
            if i > 0 and "." in module.imp:
                for parent in modules[i - 1 :: -1]:
                    if found := module.imp.startswith(f"{parent.imp}."):
                        yield (modules_idx[parent.imp], i)

                    if found or "." not in parent.imp:
                        break

    rx_g.add_edges_from_no_data(list(_iter_layered_module_edges()))

    # Add edges for imports
    for module in modules:
        module_idx = modules_idx[module.imp]
        rx_g.add_edges_from_no_data(
            [
                (module_idx, modules_idx[imported])
                for imported in grimp_g.find_modules_directly_imported_by(module.imp)
                if imported in modules_idx
            ]
        )

    return Graph(modules=modules, edges=sorted(rx_g.edge_list())).bind(rx_g)
