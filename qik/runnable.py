from __future__ import annotations

import fnmatch
import functools
import pkgutil
import re
from typing import TYPE_CHECKING, Literal, TypeAlias

import msgspec
from typing_extensions import Self

import qik.cache
import qik.conf
import qik.ctx
import qik.dep
import qik.hash
import qik.shell
import qik.unset

if TYPE_CHECKING:
    Direction: TypeAlias = Literal["up", "down"]
    Edges: TypeAlias = dict[str, set[str]]
    FilterStrategy: TypeAlias = Literal["since", "watch"]

    import qik.cache
    import qik.logger


def _make_runnable(
    *,
    cmd: str,
    conf: qik.conf.CmdConf,
    module: qik.conf.ModulePath | None = None,
) -> Runnable:
    return Runnable(
        name=f"{cmd}@{module.name}" if module else cmd,
        cmd=cmd,
        val=qik.ctx.format(conf.exec, module=module),
        deps=[
            *(qik.dep.factory(dep, module=module) for dep in conf.deps),
            *qik.dep.project_deps(),
        ],
        module=module.name if module else None,
        artifacts=[qik.ctx.format(artifact) for artifact in conf.artifacts],
        cache=qik.ctx.format(conf.cache),
        cache_when=qik.ctx.format(conf.cache_when),
    )


def factory(cmd: str, conf: qik.conf.CmdConf) -> dict[str, Runnable]:
    if "{module" in conf.exec:
        runnables = (
            _make_runnable(cmd=cmd, conf=conf, module=module)
            for module in qik.conf.project().modules_by_name.values()
        )
    else:
        runnables = [_make_runnable(cmd=cmd, conf=conf)]

    return {runnable.name: runnable for runnable in runnables}


class Result(msgspec.Struct, frozen=True):
    log: str | None
    code: int
    hash: str

    @classmethod
    def from_cache(cls, entry: qik.cache.Entry) -> Self:
        return cls(log=entry.log, code=entry.manifest.code, hash=entry.manifest.hash)


@functools.cache
def _glob_to_regex(glob_pattern: str) -> str:
    """Translate a glob to a regex pattern"""
    return fnmatch.translate(glob_pattern).replace("?s:", "^").replace(r"\Z", "$")


class Runnable(msgspec.Struct, frozen=True, dict=True):
    name: str
    cmd: str
    val: str
    shell: bool = True
    deps: list[qik.dep.BaseDep] = []
    artifacts: list[str] = []
    module: str | None = None
    cache: str | None | qik.unset.UnsetType = qik.unset.UNSET
    cache_when: qik.conf.CacheWhen | qik.unset.UnsetType = qik.unset.UNSET

    @functools.cached_property
    def deps_collection(self) -> qik.dep.Collection:
        return qik.dep.Collection(*self.deps, module=self.module)

    # TODO cache this based on the runner session
    def filter_regex(self, strategy: FilterStrategy) -> re.Pattern | None:
        """Generate the regex used for file-based filtering.

        File-based filtering occurs during --since and --watch.
        """
        globs = self.deps_collection.since if strategy == "since" else self.deps_collection.watch
        files_regex = ")|(".join(_glob_to_regex(glob) for glob in globs)
        return re.compile(f"({files_regex})", re.M) if files_regex else None

    @functools.cached_property
    def spec_hash(self) -> str:
        """Hash the runnable spec."""
        return qik.hash.val(msgspec.json.encode(self))

    def hash(self) -> str:
        """Compute the hash, including the command definitions and deps."""
        return qik.hash.strs(self.spec_hash, self.deps_collection.hash())

    def get_cache_when(self) -> qik.conf.CacheWhen:
        return (
            qik.ctx.module("qik").cache_when
            if self.cache_when is qik.unset.UNSET
            else self.cache_when
        )

    def should_cache(self, code: int) -> bool:
        match self.get_cache_when():
            case "success":
                return code == 0
            case "failed":
                return code != 0
            case "finished":
                return True
            case other:
                raise AssertionError(f'Unexpected cache_when "{other}".')

    def get_cache_backend(self) -> qik.cache.Cache:
        backend = qik.ctx.module("qik").cache if self.cache is qik.unset.UNSET else self.cache
        return qik.cache.load(backend)

    def get_cache_entry(self) -> qik.cache.Entry | None:
        if not qik.ctx.module("qik").force:
            entry = self.get_cache_backend().get(self)
            if entry and self.should_cache(entry.manifest.code):
                return entry

    def cache_result(self, result: Result) -> None:
        if self.should_cache(result.code):
            self.get_cache_backend().set(self, result)

    def _uncached_exec(self, logger: qik.logger.Logger) -> Result:
        """Run a command without wrapped caching."""
        if self.shell:
            process = qik.shell.popen(self.val)
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

        return Result(log=log, code=code, hash=self.hash())

    def _exec(self) -> Result:
        """Run a command, caching the results."""
        logger = qik.ctx.runner().logger
        cache_entry = self.get_cache_entry()
        print_kwargs = {"cache_entry": cache_entry, "runnable": self}

        if cache_entry:
            # Run cached command
            logger.print(
                msg=f"{self.name} [default][dim]{self.val}",
                emoji="fast-forward_button",
                color="cyan",
                event="start",
                **print_kwargs,
            )
            if cache_entry.log:
                logger.print(cache_entry.log, event="output", **print_kwargs)

            result = Result.from_cache(cache_entry)
        else:
            # Run uncached command
            logger.print(
                msg=f"{self.name} [default][dim]{self.val}",
                emoji="construction",
                color="cyan",
                event="start",
                **print_kwargs,
            )
            result = self._uncached_exec(logger=logger)
            self.cache_result(result)

        if result.code == 0:
            logger.print(
                msg=f"{self.name} [default][dim]{self.val}",
                emoji="white_check_mark",
                color="green",
                event="finish",
                result=result,
                **print_kwargs,
            )
        else:
            logger.print(
                msg=f"{self.name} [default][dim]{self.val}",
                emoji="broken_heart",
                color="red",
                event="finish",
                result=result,
                **print_kwargs,
            )

        return result

    def exec(self) -> Result:
        with qik.ctx.set_runnable(self), qik.ctx.set_worker_id():
            return self._exec()
