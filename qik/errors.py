from typing import TYPE_CHECKING

import qik.console

if TYPE_CHECKING:
    import qik.ctx as qik_ctx
else:
    import qik.lazy

    qik_ctx = qik.lazy.module("qik.ctx")


class Error(Exception):
    code = "general"


class ConfigNotFound(Error):
    code = "conf0"


class ModulePathNotFound(Error):
    code = "conf1"


class ModuleNotFound(Error):
    code = "conf2"


class PluginNotFound(Error):
    code = "conf3"


class ModuleOrPluginNotFound(Error):
    code = "conf4"


class CommandNotFound(Error):
    code = "conf5"


class PluginImport(Error):
    code = "conf6"


class GraphCycle(Error):
    code = "conf7"


class UnconfiguredCache(Error):
    code = "cache0"


class InvalidCacheType(Error):
    code = "cache1"


class CtxProfileNotFound(Error):
    code = "ctx0"


class EnvCast(Error):
    code = "ctx1"


class CtxValueNotFound(Error):
    code = "ctx2"


class UnconfiguredCtx(Error):
    code = "ctx3"


class InvalidCtxNamespace(Error):
    code = "ctx4"


class LockFileNotFound(Error):
    code = "venv0"


class VenvNotFound(Error):
    code = "venv1"


def print(exc: Exception) -> None:
    print_err_kwargs = {"emoji": "broken_heart", "color": "red"}
    if isinstance(exc, Error):
        if qik_ctx.module("qik").verbosity >= 3:
            qik.console.print_exception()

        qik.console.print(
            f"{exc.args[0]} [reset][dim]https://qik.build/en/stable/errors/#{exc.code}[/dim]",
            **print_err_kwargs,
        )
    else:
        qik.console.print("An unexpected error happened.", **print_err_kwargs)
        qik.console.print_exception()
