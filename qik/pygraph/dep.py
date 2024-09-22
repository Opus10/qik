from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import qik.conf
import qik.ctx
import qik.dep
import qik.pygraph.utils

if TYPE_CHECKING:
    from qik.pygraph.qikplugin import PygraphDepConf


class PygraphDep(qik.dep.BaseCmd, frozen=True):
    """A python module and its associated imports."""

    strict: ClassVar[bool] = True  # type: ignore
    space: str | None = None

    def get_cmd_name(self) -> str:
        return qik.pygraph.utils.lock_cmd_name()

    def get_cmd_args(self) -> dict[str, str | None]:
        return {"pyimport": self.val, "space": self.space}

    @property
    def globs(self) -> list[str]:  # type: ignore
        return [str(qik.pygraph.utils.lock_path(self.val, self.space))]


def factory(
    conf: PygraphDepConf,
    module: qik.conf.ModuleLocator | None = None,
    space: str | None = None,
) -> PygraphDep:
    return PygraphDep(qik.ctx.format(conf.pyimport, module=module), space=space)
