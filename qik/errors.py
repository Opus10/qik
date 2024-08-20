from typing import TYPE_CHECKING

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


class ModulePathNotFound(RunnerError):
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


class UnconfiguredCache(RunnerError):
    code = "cache0"


class InvalidCacheType(RunnerError):
    code = "cache1"


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


class LockFileNotFound(RunnerError):
    code = "venv0"


class VenvNotFound(RunnerError):
    code = "venv1"


class RunnableError(Error):
    """Runnable errors result in an individual runnable erroring."""

    code = "runnable"


class ModuleDistributionNotFound(RunnableError):
    code = "graph0"


class DistributionNotFound(RunnableError):
    code = "dep0"


def fmt_msg(exc: Exception) -> str:
    err_kwargs = (
        {} if isinstance(exc, RunnableError) else {"emoji": "broken_heart", "color": "red"}
    )
    if isinstance(exc, Error):
        return qik.console.fmt_msg(
            f"{exc.args[0]} [reset][dim]See https://qik.build/en/stable/errors/#{exc.code}[/dim]",
            **err_kwargs,
        )
    else:
        return qik.console.fmt_msg("An unexpected error happened", **err_kwargs)


def print(exc: Exception) -> None:
    msg = fmt_msg(exc)
    qik.console.get().print(msg)
    if not isinstance(exc, Error) or qik_ctx.module("qik").verbosity >= 3:
        qik.console.print_exception()
