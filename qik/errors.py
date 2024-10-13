import contextlib
import sys
from typing import TYPE_CHECKING, Iterator

import qik.console

if TYPE_CHECKING:
    import qik.ctx as qik_ctx
else:
    import qik.lazy

    qik_ctx = qik.lazy.module("qik.ctx")


class Error(Exception):
    code = "general"


class RunnerError(Error):
    """Runner errors result in the whole runner exiting."""

    code = "runner"


class ConfigNotFound(RunnerError):
    code = "conf0"


class ConfigParse(RunnerError):
    code = "conf1"


class ModuleNotFound(RunnerError):
    code = "conf2"


class PluginNotFound(RunnerError):
    code = "conf3"


class ModuleOrPluginNotFound(RunnerError):
    code = "conf4"


class CommandNotFound(RunnerError):
    code = "conf5"


class PluginImport(RunnerError):
    code = "conf6"


class GraphCycle(RunnerError):
    code = "conf7"


class SpaceNotFound(RunnerError):
    code = "conf8"


class UnconfiguredCache(RunnerError):
    code = "conf9"


class InvalidCacheType(RunnerError):
    code = "conf10"


class InvalidDepType(RunnerError):
    code = "conf11"


class InvalidVenvType(RunnerError):
    code = "conf12"


class CircularVenv(RunnerError):
    code = "conf13"


class CircularConstraint(RunnerError):
    code = "conf14"


class CircularFence(RunnerError):
    code = "conf14"


class CtxProfileNotFound(RunnerError):
    code = "ctx0"


class EnvCast(RunnerError):
    code = "ctx1"


class CtxValueNotFound(RunnerError):
    code = "ctx2"


class UnconfiguredCtx(RunnerError):
    code = "ctx3"


class InvalidCtxNamespace(RunnerError):
    code = "ctx4"


class ArgNotSupplied(RunnerError):
    code = "args0"


class RunnableError(Error):
    """Runnable errors result in an individual runnable erroring."""

    code = "runnable"


class LockFileNotFound(RunnableError):
    code = "space0"


class VenvNotFound(RunnableError):
    code = "space1"


class DotEnvNotFound(RunnableError):
    code = "space2"


class DistributionNotFound(RunnableError):
    code = "pydist0"


def fmt_msg(exc: Exception, prefix: str = "") -> str:
    err_kwargs = (
        {} if isinstance(exc, RunnableError) else {"emoji": "broken_heart", "color": "red"}
    )
    if isinstance(exc, Error):
        return qik.console.fmt_msg(
            f"{prefix}{exc.args[0]} [reset][dim]See https://qik.build/en/stable/errors/#{exc.code}[/dim]",
            **err_kwargs,  # type: ignore
        )
    else:
        return qik.console.fmt_msg("An unexpected error happened", **err_kwargs)  # type: ignore


def print(exc: Exception, prefix: str = "") -> None:
    msg = fmt_msg(exc, prefix=prefix)
    qik.console.get().print(msg)
    if not isinstance(exc, Error) or qik_ctx.by_namespace("qik").verbosity >= 3:
        qik.console.print_exception()


@contextlib.contextmanager
def catch_and_exit() -> Iterator[None]:
    try:
        yield
    except Error as e:
        print(e)
        sys.exit(1)
