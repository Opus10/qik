from __future__ import annotations

import contextlib
import functools
from typing import TYPE_CHECKING, Any, Iterator, Literal, TypeAlias

import qik.lazy

if TYPE_CHECKING:
    import rich.console as rich_console

    Emoji: TypeAlias = Literal[
        "broken_heart",
        "construction",
        "eyes",
        "white_check_mark",
        "fast-forward_button",
        "heavy_minus_sign",
    ]
    Color: TypeAlias = Literal["cyan", "red", "green", "yellow"]
else:
    rich_console = qik.lazy.module("rich.console")


def print(msg: str, emoji: Emoji | None = None, color: Color | None = None, **kwargs: Any) -> None:
    if color:
        msg = f"[{color}]{msg}[/{color}]"

    if emoji:
        msg = f":{emoji}-emoji: {msg}"

    get().print(msg, **kwargs)


def print_exception() -> None:
    get().print_exception()


def rule(
    title: str = "",
    *,
    style: str = "rule.line",
    align: Literal["left", "center", "right"] = "left",
) -> None:
    get().rule(title, align=align, style=style)


@contextlib.contextmanager
def capture() -> Iterator[None]:
    with get().capture():
        yield


@functools.cache
def get() -> rich_console.Console:
    return qik.lazy.object(rich_console.Console)  # type: ignore
