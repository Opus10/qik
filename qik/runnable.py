from __future__ import annotations

import fnmatch
import pkgutil
import re
from typing import TYPE_CHECKING, Literal, TypeAlias

import msgspec
from typing_extensions import Self

import qik.cache
import qik.conf
import qik.ctx
import qik.dep
import qik.errors
import qik.file
import qik.func
import qik.hash
import qik.shell
import qik.space
import qik.unset
import qik.venv

if TYPE_CHECKING:
    Direction: TypeAlias = Literal["up", "down"]
    Edges: TypeAlias = dict[str, set[str]]
    FilterStrategy: TypeAlias = Literal["since", "watch"]

    import pathlib

    import qik.cache
    import qik.logger
    import qik.venv


class DepsCollection:
    """A filterable and hashable collection of dependencies for a runnable."""

    def __init__(self, *deps: str | pathlib.Path | qik.dep.Dep, runnable: Runnable):
        self._deps = [
            dep if isinstance(dep, qik.dep.Dep) else qik.dep.Glob(str(dep)) for dep in deps
        ]
        self.runnable = runnable
        self.module = runnable.module
        self.space_globs = runnable.resolved_space.glob_deps if runnable.resolved_space else set()
        self.venv = runnable.resolved_venv

    @property
    def globs(self) -> set[str]:
        return (
            {glob for dep in self._deps for glob in dep.globs}
            | {
                artifact
                for runnable in self.runnables.values()
                for artifact in runnable.obj.artifacts
            }
            | self.venv.glob_deps
            | self.space_globs
        )

    @qik.func.cached_property
    def consts(self) -> set[str]:
        return {
            dep.val for dep in self._deps if isinstance(dep, qik.dep.Const)
        } | self.venv.const_deps

    @qik.func.cached_property
    def watch(self) -> set[str]:
        return {glob for dep in self._deps for glob in dep.watch}

    @qik.func.cached_property
    def since(self) -> set[str]:
        venv_since = self.venv.since_deps if self.runnable.space else set()
        return {glob for dep in self._deps for glob in dep.since} | venv_since

    @property
    def vals(self) -> set[str]:
        return {val for dep in self._deps for val in dep.vals}

    @property
    def pydists(self) -> set[str]:
        return {pydist for dep in self._deps for pydist in dep.pydists}

    @property
    def runnables(self) -> dict[str, qik.dep.Runnable]:
        return {
            runnable.name: runnable
            for dep in self._deps
            for runnable in dep.runnables
            if not self.module or not runnable.obj.module or self.module == runnable.obj.module
        } | self.venv.runnable_deps

    @qik.func.cached_property
    def consts_hash(self) -> str:
        """Hash all consts."""
        return qik.hash.strs(*self.consts)

    def hash_vals(self) -> str:
        """Hash file values."""
        return qik.hash.strs(*self.vals)

    def hash_pydists(self) -> str:
        """Hash python distributions."""
        return qik.hash.pydists(*self.pydists, venv=self.venv)

    def hash_globs(self) -> str:
        """Hash glob pattern."""
        return qik.hash.globs(*self.globs)

    def hash(self) -> str:
        """The full hash."""
        return qik.hash.strs(
            self.consts_hash, self.hash_vals(), self.hash_globs(), self.hash_pydists()
        )


@qik.func.cache
def _num_spaces() -> int:
    return len((set(qik.conf.project().resolved_spaces) | {"default"}))


def fmt_name(
    cmd: str,
    *,
    module: qik.conf.ModuleLocator | None = None,
    space: str | None = "default",
    **args: str,
) -> str:
    module_str = f"#{module.name}" if module else ""
    space_str = f"@{space}" if space and _num_spaces() > 1 else ""
    args_str = "?" + "&".join(f"{k}={v}" for k, v in args.items()) if args else ""
    return f"{cmd}{space_str}{module_str}{args_str}"


def _make_runnable(
    *,
    cmd: str,
    conf: qik.conf.Cmd,
    space: str | None,
    module: qik.conf.ModuleLocator | None = None,
) -> Runnable:
    # If the command has no deps, use "none" as the cache unless explicitly set
    initial_cache = "none" if not conf.deps else conf.cache

    return Runnable(
        name=fmt_name(cmd, module=module, space=space),
        cmd=cmd,
        val=qik.ctx.format(conf.exec, module=module),
        deps=[
            *qik.dep.base(),
            *(qik.dep.factory(dep, module=module, space=space) for dep in conf.deps),
        ],
        module=module.name if module else None,
        artifacts=[qik.ctx.format(artifact) for artifact in conf.artifacts],
        cache=qik.ctx.format(
            qik.unset.coalesce(initial_cache, qik.conf.project().defaults.cache, default="local")
        ),
        cache_when=qik.ctx.format(
            qik.unset.coalesce(
                conf.cache_when, qik.conf.project().defaults.cache_when, default="success"
            )
        ),  # type: ignore
        space=space,
    )


def factory(cmd: str, conf: qik.conf.Cmd, **args: str) -> dict[str, Runnable]:
    """The main factory for creating runnables.

    We don't preserve **args in the made runnables because generic runnables do not
    yet support args. Only custom runnables do.
    """
    if "{module" in conf.exec:
        proj = qik.conf.project()
        if not isinstance(conf.space, qik.unset.UnsetType):
            spaces = {conf.space: qik.space.load(conf.space).conf}
        else:
            spaces = proj.resolved_spaces

        runnables = (
            _make_runnable(cmd=cmd, conf=conf, module=module, space=space)
            for space, space_conf in spaces.items()
            for module in space_conf.modules_by_name.values()
        )
    else:
        space = conf.space if not isinstance(conf.space, qik.unset.UnsetType) else "default"
        runnables = [_make_runnable(cmd=cmd, conf=conf, space=space)]

    return {runnable.name: runnable for runnable in runnables}


class Result(msgspec.Struct, frozen=True):
    log: str | None
    code: int
    hash: str

    @classmethod
    def from_cache(cls, entry: qik.cache.Entry) -> Self:
        return cls(log=entry.log, code=entry.manifest.code, hash=entry.manifest.hash)


@qik.func.cache
def _glob_to_regex(glob_pattern: str) -> str:
    """Translate a glob to a regex pattern"""
    return fnmatch.translate(glob_pattern).replace("?s:", "^").replace(r"\Z", "$")


class Runnable(msgspec.Struct, frozen=True, dict=True):
    name: str
    cmd: str
    val: str
    cache: str
    cache_when: qik.conf.CacheWhen
    shell: bool = True
    deps: list[qik.dep.Dep] = []
    artifacts: list[str] = []
    module: str | None = None
    args: dict[str, str] = {}
    space: str | None = None
    venv: qik.unset.UnsetType | None = qik.unset.UNSET
    environ: dict[str, str] = {}

    @qik.func.per_run_cached_property
    def description(self) -> str:
        args = ", ".join(f"{k}={v}" for k, v in self.args.items())
        return f"{self.val}({args})" if args and not self.shell else self.val

    @qik.func.cached_property
    def slug(self) -> str:
        return re.sub(r"[^a-zA-Z0-9]", "__", self.name)

    @qik.func.cached_property
    def deps_collection(self) -> DepsCollection:
        return DepsCollection(*self.deps, runnable=self)

    @qik.func.cached_property
    def resolved_space(self) -> qik.space.Space | None:
        return qik.space.load(self.space) if self.space else None

    @qik.func.cached_property
    def resolved_venv(self) -> qik.venv.Venv:
        if not self.resolved_space or self.venv is None:
            return qik.venv.active()
        else:
            return self.resolved_space.venv

    @qik.func.cached_property
    def resolved_environ(self) -> dict[str, str]:
        base_environ = (
            self.resolved_venv.environ if not self.resolved_space else self.resolved_space.environ
        )
        return {**base_environ, **self.environ}

    @property
    def _exec_env(self) -> dict[str, str]:
        """Get the environment for runnables."""
        return {
            **self.resolved_environ,
            "QIK__CMD": self.cmd,
            "QIK__RUNNABLE": self.name,
            "QIK__WORKER": str(qik.ctx.worker_id()),
        }

    def filter_regex(self, strategy: FilterStrategy) -> re.Pattern | None:
        """Generate the regex used for file-based filtering.

        File-based filtering occurs during --since and --watch.
        """
        globs = self.deps_collection.since if strategy == "since" else self.deps_collection.watch
        files_regex = ")|(".join(_glob_to_regex(glob) for glob in globs)
        return re.compile(f"({files_regex})", re.M) if files_regex else None

    @qik.func.cached_property
    def spec_hash(self) -> str:
        """Hash the runnable spec."""
        # Note - we don't include caching arguments in the definition hash since they don't materially
        # affect the outcome.
        return qik.hash.val(
            msgspec.json.encode(msgspec.structs.replace(self, cache="", cache_when=""))
        )

    def hash(self) -> str:
        """Compute the hash, including the command definitions and deps."""
        return qik.hash.strs(self.spec_hash, self.deps_collection.hash())

    def should_cache(self, code: int) -> bool:
        match self.cache_when:
            case "success":
                return code == 0
            case "failed":
                return code != 0
            case "finished":
                return True
            case other:
                raise AssertionError(f'Unexpected cache_when "{other}".')

    def get_cache_backend(self) -> qik.cache.Cache:
        return qik.cache.load(self.cache)

    def get_cache_entry(self, artifacts: bool = True) -> qik.cache.Entry | None:
        if not qik.ctx.by_namespace("qik").force:
            entry = self.get_cache_backend().get(self, artifacts=artifacts)
            if entry and self.should_cache(entry.manifest.code):
                return entry

    def cache_result(self, result: Result) -> None:
        if self.should_cache(result.code):
            self.get_cache_backend().set(self, result)

    def store_deps(
        self,
        path: pathlib.Path,
        *,
        globs: list[str] | None = None,
        pydists: list[str] | None = None,
        hash: bool = True,
    ) -> None:
        """Store serialized dependencies for a runnable."""
        if hash:
            hash_val = DepsCollection(
                *[*(globs or []), *[qik.dep.Pydist(val=pydist) for pydist in pydists or []]],
                runnable=self,
            ).hash()
        else:
            hash_val = None

        qik.file.write(
            path,
            msgspec.json.encode(
                qik.dep.Serialized(globs=globs or [], pydists=pydists or [], hash=hash_val)
            ),
        )

    def _uncached_exec(self, logger: qik.logger.Logger) -> Result:
        """Run a command without wrapped caching."""
        try:
            if self.shell:
                process = qik.shell.popen(self.val, env=self._exec_env)
                output = []
                for line in process.stdout if process.stdout is not None else []:
                    logger.print(line, runnable=self, event="output")
                    output.append(line)

                process.wait()
                code = process.returncode
                log = "".join(output)
            else:
                code, log = pkgutil.resolve_name(self.val)(runnable=self)
                logger.print(log, runnable=self, event="output")
        except qik.errors.RunnableError as exc:
            log = qik.errors.fmt_msg(exc)
            code = 1
            logger.print(log, runnable=self, event="output")

        return Result(log=log, code=code, hash=self.hash())

    def _exec(self) -> Result:
        """Run a command, caching the results."""
        logger = qik.ctx.runner().logger
        print_kwargs = {"runnable": self}

        def _log_start(cached: bool) -> None:
            if cached:
                logger.print(
                    msg=f"{self.name} [default][dim]{self.description}",
                    emoji="fast-forward_button",
                    color="cyan",
                    event="start",
                    **print_kwargs,  # type: ignore
                )
            else:
                logger.print(
                    msg=f"{self.name} [default][dim]{self.description}",
                    emoji="construction",
                    color="cyan",
                    event="start",
                    **print_kwargs,  # type: ignore
                )

        try:
            cache_entry = self.get_cache_entry()
        except qik.errors.RunnableError as exc:
            _log_start(cached=False)
            log = qik.errors.fmt_msg(exc)
            logger.print(f"{log}", runnable=self, event="output")
            result = Result(log=log, code=1, hash="")
        else:
            print_kwargs |= {"cache_entry": cache_entry}

            if cache_entry:
                # Run cached command
                _log_start(cached=True)
                logger.print(cache_entry.log or "", event="output", **print_kwargs)  # type: ignore
                result = Result.from_cache(cache_entry)
            else:
                # Run uncached command
                _log_start(cached=False)
                result = self._uncached_exec(logger=logger)
                self.cache_result(result)

        if result.code == 0:
            logger.print(
                msg=f"{self.name} [default][dim]{self.description}",
                emoji="white_check_mark",
                color="green",
                event="finish",
                result=result,
                **print_kwargs,  # type: ignore
            )
        else:
            logger.print(
                msg=f"{self.name} [default][dim]{self.description}",
                emoji="broken_heart",
                color="red",
                event="finish",
                result=result,
                **print_kwargs,  # type: ignore
            )

        return result

    def exec(self) -> Result:
        with qik.ctx.set_runnable(self), qik.ctx.set_worker_id():
            return self._exec()
